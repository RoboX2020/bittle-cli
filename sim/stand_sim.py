#!/usr/bin/env python3
"""Planar simulation of a Bittle on two legs (handstand or rear stand), to pick starting PID gains
and to see how much control delay (onboard vs USB vs Bluetooth/WiFi) the stand tolerates.

Model (side view):
  paw     : flat contact of half-length R. While the centre of pressure stays inside the paw, the
            support leg is held still by the floor and the shoulder moves the body directly. Once
            the weight passes the paw's edge, the whole robot tips about that edge.
  leg     : support leg, length L1 from paw to shoulder, light
  body    : mass MB at L2 from the shoulder along the body, inertia I
  air legs: mass MA at the far end of the body (LB from the shoulder), length LA, swung by
            their own shoulder joints (the firmware's "air" gain), like a counterweight
  servos  : first-order lag TAU with speed limit WMAX
  IMU     : body pitch with noise, delayed by the sensor filter plus the control link
  PID     : the same law as firmware/balanceStand.h

Numbers in PARAMS are estimates, not measurements. Use the results as starting points and to
compare links, not as final gains.

  python3 stand_sim.py              # paw contact size vs controllers (about a minute)
  python3 stand_sim.py --links      # also compares onboard / USB / BLE / WiFi control
"""
import argparse, math, random

PARAMS = dict(
    MB=0.25, MA=0.04,           # kg: body + head + support legs, the two airborne legs
    L1=0.085, L2=0.07,          # m: paw->shoulder, shoulder->body COM
    LB=0.11, LA=0.07,           # m: shoulder->other hip, airborne leg length
    I=0.25 * 0.2 ** 2 / 12,     # kg m^2: body as a 20 cm rod
    R=0.004,                    # m: half-length of the paw contact patch
    TAU=0.035,                  # s: servo position lag under load
    WMAX=math.radians(350),     # rad/s: servo speed under load
    NOISE=0.3,                  # deg: IMU pitch noise
)

# Delay from "body moves" to "servo gets the new command", and the controller period.
LINKS = {
    "onboard (firmware PID)": dict(delay=0.012, tick=0.005),
    "laptop over USB serial": dict(delay=0.030, tick=0.010),
    "laptop over BLE":        dict(delay=0.075, tick=0.015),
    "laptop over WiFi":       dict(delay=0.090, tick=0.020),
}
G = (0.0, -9.81)
G0 = math.radians(25)       # base shoulder angle between support leg and body
GA0 = math.radians(150)     # base angle of the airborne legs relative to the body


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def points(d, g, ga, edge, p):
    """Body COM and airborne-leg COM relative to the pivot, and the body angle.
    d = lean of the support leg from vertical, edge = x of the pivot on the paw (-R, 0 or R)."""
    L1, L2, LB, LA = p["L1"], p["L2"], p["LB"], p["LA"]
    shx, shy = -edge + L1 * math.sin(d), L1 * math.cos(d)
    b = d + g                                # body angle from vertical
    body = (shx + L2 * math.sin(b), shy + L2 * math.cos(b))
    hip = (shx + LB * math.sin(b), shy + LB * math.cos(b))
    air = (hip[0] + LA * math.sin(b + ga), hip[1] + LA * math.cos(b + ga))
    return body, air, b


def accel_terms(d, dd, g, gd, ga, gad, edge, p, eps=1e-4):
    """For each point: position, d/d(d) Jacobian, and the velocity-product acceleration."""
    out = []
    base = points(d, g, ga, edge, p)
    plus = points(d + eps, g, ga, edge, p)
    fwd = points(d + dd * eps, g + gd * eps, ga + gad * eps, edge, p)
    bwd = points(d - dd * eps, g - gd * eps, ga - gad * eps, edge, p)
    for k in range(2):
        pos = base[k]
        J = ((plus[k][0] - pos[0]) / eps, (plus[k][1] - pos[1]) / eps)
        h = ((fwd[k][0] - 2 * pos[0] + bwd[k][0]) / eps ** 2, (fwd[k][1] - 2 * pos[1] + bwd[k][1]) / eps ** 2)
        out.append((pos, J, h))
    return out


def joint_accel_points(d, g, ga, gdd, gadd, edge, p, eps=1e-4):
    """Acceleration of each point caused by the joint accelerations alone."""
    base = points(d, g, ga, edge, p)
    pg = points(d, g + eps, ga, edge, p)
    pa = points(d, g, ga + eps, edge, p)
    return [(((pg[k][0] - base[k][0]) * gdd + (pa[k][0] - base[k][0]) * gadd) / eps,
             ((pg[k][1] - base[k][1]) * gdd + (pa[k][1] - base[k][1]) * gadd) / eps) for k in range(2)]


def balanced_lean(p):
    """Support-leg lean that puts the base pose's COM over the paw centre."""
    m = (p["MB"], p["MA"])
    def com_x(d):
        bd, ar, _ = points(d, G0, GA0, 0.0, p)
        return (m[0] * bd[0] + m[1] * ar[0]) / sum(m)
    lo, hi = -1.2, 1.2
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if com_x(mid) * com_x(lo) > 0 else (lo, mid)
    return (lo + hi) / 2


def simulate(kp, ki, kd, link, air=0.0, mix=1.0, pose_err=0.0, T=3.0, sign=1, sp_error=0.3, start_tilt=0.0,
             push_at=1.0, push=0.004, seed=1, limit=30, d_alpha=0.35, fall=35, trace=False, p=PARAMS):
    """Returns (seconds held, rms pitch error deg, max |u| deg, trace)."""
    rnd = random.Random(seed)
    dt = 0.0005
    m = (p["MB"], p["MA"])
    flat_d = balanced_lean(p)                # leg lean while the paw is flat
    b_eq = math.degrees(flat_d + G0)
    base = G0 + math.radians(pose_err)      # the top pose is off by pose_err degrees
    # "yz" is captured while the paws are flat on the floor (held by hand), with a small error
    setpoint = math.degrees(flat_d + base) + sp_error
    g, ga, gd, gad = base, GA0, 0.0, 0.0
    gcmd, gacmd = g, ga
    edge, d, dd = 0.0, flat_d, 0.0
    if start_tilt:                           # start already tipping on an edge
        edge = math.copysign(p["R"], start_tilt)
        d = flat_d + math.radians(start_tilt)
    integ = prev_err = dfilt = 0.0
    first = True
    buf, next_tick, t = [], 0.0, 0.0
    sq = n = 0
    umax = 0.0
    tr = []
    while t < T:
        buf.append((t + link["delay"], math.degrees(d + g) + rnd.gauss(0, p["NOISE"])))
        if t >= next_tick:
            next_tick += link["tick"]
            meas = None
            while buf and buf[0][0] <= t:
                meas = buf.pop(0)[1]
            if meas is not None:
                # mix blends body pitch (0) towards support-leg tilt (1): pitch minus the shoulder
                # offset already commanded, i.e. how far the paw itself has tipped
                err = meas - setpoint - mix * math.degrees(gcmd - base)
                dv = 0 if first else (err - prev_err) / link["tick"]
                first, prev_err = False, err
                dfilt += d_alpha * (dv - dfilt)
                pd = kp * err + kd * dfilt
                inext = integ + err * link["tick"]
                if abs(pd + ki * inext) < limit:
                    integ = inext
                u = max(-limit, min(limit, sign * (pd + ki * integ)))
                umax = max(umax, abs(u))
                gcmd = base + math.radians(u)
                gacmd = GA0 + math.radians(air * u)
        # servos
        ngd = max(-p["WMAX"], min(p["WMAX"], (gcmd - g) / p["TAU"]))
        ngad = max(-p["WMAX"], min(p["WMAX"], (gacmd - ga) / p["TAU"]))
        gdd, gadd = (ngd - gd) / dt, (ngad - gad) / dt
        gd, gad = ngd, ngad
        fx = push / 0.02 if push_at <= t < push_at + 0.02 else 0.0   # shove on the body, N
        terms = accel_terms(d, dd, g, gd, ga, gad, edge, p)
        jac = joint_accel_points(d, g, ga, gdd, gadd, edge, p)
        ddd = 0.0
        if edge == 0.0:
            # paw flat: is the centre of pressure still inside the paw?
            tau = N = 0.0
            for k in range(2):
                pos, _, h = terms[k]
                acc = (h[0] + jac[k][0], h[1] + jac[k][1])
                f = (m[k] * (acc[0] - G[0]) - (fx if k == 0 else 0.0), m[k] * (acc[1] - G[1]))
                tau += cross(pos, f)
                N += f[1]
            tau += p["I"] * gdd
            cop = tau / N if N > 1e-6 else 1.0
            if abs(cop) > p["R"]:
                edge = math.copysign(p["R"], cop)   # weight passed the paw edge
                terms = accel_terms(d, dd, g, gd, ga, gad, edge, p)
                jac = joint_accel_points(d, g, ga, gdd, gadd, edge, p)
        if edge != 0.0:
            # tipping about the edge: rate of angular momentum about the pivot = gravity + push torque
            lhs, rhs = p["I"], -p["I"] * gdd
            for k in range(2):
                pos, J, h = terms[k]
                lhs += m[k] * cross(pos, J)
                rhs += m[k] * (cross(pos, G) - cross(pos, (h[0] + jac[k][0], h[1] + jac[k][1])))
            rhs += cross(terms[0][0], (fx, 0.0))
            ddd = rhs / lhs
        dd += ddd * dt
        d += dd * dt
        g += gd * dt
        ga += gad * dt
        if edge != 0.0 and (d - flat_d) * math.copysign(1, edge) <= 0:
            d, dd, edge = flat_d, 0.0, 0.0       # paw lands flat again (no bounce)
        t += dt
        e = math.degrees(d - flat_d)          # how far the paw has tipped
        sq += e * e
        n += 1
        if trace and n % 20 == 0:
            tr.append((t, e, math.degrees(g - base), edge != 0.0))
        if abs(e) > 25 or abs(math.degrees(d + g) - b_eq) > fall:
            return t, math.sqrt(sq / n), umax, tr
    return T, math.sqrt(sq / n), umax, tr


ON = LINKS["onboard (firmware PID)"]
CONTROLLERS = {                    # (kp, ki, kd, sign, mix)
    "no control (hold pose)": (0, 0, 0, 1, 0.0),
    "PID on body pitch": (1, 0, 0.05, -1, 0.0),
    "PID on leg tilt": (2, 0, 0.1, 1, 1.0),
}


def pose_window(p):
    """Largest top-pose error (deg, both directions) the robot holds without control."""
    ok = 0
    for pe in range(1, 30):
        if all(simulate(0, 0, 0, ON, pose_err=sg * pe, push=0, p=p)[0] >= 3 for sg in (1, -1)):
            ok = pe
        else:
            break
    return ok


def max_push(p, ctl, link=ON):
    """Largest shove (impulse, mN s, either direction) survived with top-pose errors of -1, 0, +1 deg."""
    def holds(push):
        return all(simulate(*ctl[:3], link, sign=ctl[3], mix=ctl[4], pose_err=pe, push=pk * push, seed=i, p=p)[0] >= 3
                   for i, pe in enumerate((-1, 0, 1)) for pk in (1, -1))
    if not holds(0):
        return 0.0
    lo, hi = 0.0, 0.3
    for _ in range(8):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if holds(mid) else (lo, mid)
    return lo * 1000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--paws", default="4,8,16,30,50", help="paw contact lengths to compare, mm")
    ap.add_argument("--links", action="store_true", help="also compare control links (slow)")
    a = ap.parse_args()
    names = list(CONTROLLERS)
    print(f"{'paw contact':>11s} {'pose window':>12s}  " + "  ".join(f"{n:>22s}" for n in names))
    for mm in (float(x) for x in a.paws.split(",")):
        p = dict(PARAMS, R=mm / 2000)
        pushes = [max_push(p, CONTROLLERS[n]) for n in names]
        print(f"{mm:8.0f} mm {'±%d°' % pose_window(p):>12s}  " + "  ".join(f"{x:17.1f} mN s" for x in pushes))
    print("pose window: top-pose error that still stands untouched. Columns: largest shove survived.")
    if a.links:
        p = dict(PARAMS, R=0.025)
        print("\nwith 50 mm contact, PID on body pitch, by control link:")
        for name, link in LINKS.items():
            print(f"  {name:24s} {max_push(p, CONTROLLERS[names[1]], link):6.1f} mN s")


if __name__ == "__main__":
    main()
