"""agents-inc demo clip, v6: "Run your AI like a company" (spec 049).

Render:  manim -qh --media_dir demo/clip/media demo/clip/scene.py CompanyV6

Everything on screen is an illustration of how agents-inc works; no run data
is shown. The one value read from the recorded runs is the provider "kind" of
runs/format/run.json (the caught Worker's ring) and runs/review/run.json (the
reviewer's ring), so that the two differ as they did in the run this clip is
modelled on.

Rules the picture respects (docs/governance/DELEGATION-MODEL.md, CONTEXT.md,
docs/DECISIONS.md D78): the Executive talks to you and delegates; review sits
at the Orchestrator rung (the reviewer is the Orchestrator's sibling); a
Workhorse-rung Worker delegates only to Grunts; Grunts never delegate; free
models only ever do Grunt work, so the free-model ring appears on Grunts only.
Avatars are cut from docs/assets/logo-wide.png by make_avatars.py.
"""
import json
import os

import numpy as np
from manim import (ORIGIN, DOWN, LEFT, RIGHT, UP, UR, AnimationGroup, Circle, Create, DashedLine,
                   Dot, FadeIn, FadeOut, GrowFromCenter, Group, ImageMobject, Line,
                   MoveAlongPath, RoundedRectangle, Scene, Succession, Text, TracedPath,
                   VGroup, Wait, config, rate_functions)

config.pixel_width = 1920
config.pixel_height = 1080
config.frame_rate = 30

NAVY = "#0a0d26"
BLUE, LIME, AMBER, PINK, RED, CORAL, GREEN = (
    "#3fa9ff", "#a6e22e", "#ffb938", "#ff6fcf", "#ff4b5c", "#ff8a4c", "#3ddc84")
WHITE, SOFT, OFF, EDGEC = "#ffffff", "#c9d1ff", "#2a3050", "#34407a"
config.background_color = NAVY

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
SANS = "Avenir Next"
EDGE = 0.6

PROVIDER = {"claude": CORAL, "codex": BLUE}
FREE = PINK
LEGEND = [("Claude", CORAL), ("Codex", BLUE), ("free models", FREE)]

# Fixed text.
BADGE = "Illustration"
CAPS = {
    "hook": ["Run your AI", "like a company."],
    "think": ["Think it", "through together."],
    "plan": ["Plan first.", "Then delegate."],
    "check": ["Checked.", "Then reviewed."],
    "many": ["One chief of staff.", "Many projects."],
}
ALIAS = {"you": "the CEO", "executive": "your chief of staff", "orchestrator": "project manager",
         "reviewer": "second opinion", "worker": "does the work", "grunt": "quick errands"}
TAG = ["Run your AI subscriptions", "like a small company"]
WORDMARK, MATURITY = "agents-inc", "Experimental"
LINK = "github.com/domattioli/agents-inc"


def kind(name):
    with open(os.path.join(HERE, "runs", name, "run.json"), encoding="utf-8") as f:
        return json.load(f)["kind"]


def S(s, size, color=WHITE, weight="HEAVY"):
    return Text(s, font=SANS, font_size=size, color=color, weight=weight)


def card(color=AMBER, w=0.42, h=0.3):
    body = RoundedRectangle(width=w, height=h, corner_radius=0.05, fill_color=color,
                            fill_opacity=1, stroke_width=0)
    lines = VGroup(*[Line(LEFT * w * 0.3, RIGHT * w * (0.3 - 0.12 * k), stroke_width=3,
                          color="#00000088").shift(UP * h * (0.2 - 0.23 * k)) for k in range(3)])
    return VGroup(body, lines.move_to(body))


def bubble(w):
    b = RoundedRectangle(width=w, height=w * 0.62, corner_radius=w * 0.25, fill_color=WHITE,
                         fill_opacity=1, stroke_width=0)
    dots = VGroup(*[Dot(radius=w * 0.06, color=NAVY) for _ in range(3)]).arrange(RIGHT, buff=w * 0.1)
    return VGroup(b, dots.move_to(b))


class Node:
    def __init__(self, avatar, pos, r, ring):
        self.img = ImageMobject(os.path.join(ASSETS, avatar + ".png")).set_height(2 * r).move_to(pos)
        self.ring = Circle(radius=r + 0.05, stroke_color=OFF, stroke_width=7).move_to(pos)
        self.glow = Circle(radius=r + 0.05, stroke_color=ring, stroke_width=26, stroke_opacity=0).move_to(pos)
        self.img.set_opacity(0.18)
        self.r0, self.col = r, ring

    @property
    def pos(self):
        return self.ring.get_center()

    @property
    def r(self):
        return self.ring.width / 2 - 0.05

    def parts(self):
        return [self.glow, self.ring, self.img]

    def on(self):
        return [self.img.animate.set_opacity(1), self.ring.animate.set_stroke(self.col, opacity=1)]


def ends(a, b):
    u = (b.pos - a.pos) / np.linalg.norm(b.pos - a.pos)
    return a.pos + u * a.r, b.pos - u * b.r


def team(ox, oy, s, cw, cr, worker_ring, grunt_rings):
    """Orchestrator + reviewer + 3 Workers + 5 Grunts, Orchestrator centred at (ox, oy), scale s."""
    orc = Node("orchestrator", [ox, oy, 0], 0.42 * s, cr)
    rev = Node("reviewer", [ox + 2.4 * s, oy, 0], 0.42 * s, cr)
    wx = [ox - 1.5 * s, ox, ox + 1.5 * s]
    workers = [Node("workhorse", [x, oy - 1.45 * s, 0], 0.36 * s, c) for x, c in zip(wx, worker_ring)]
    gpos = [[-0.55, 0.55], [0.0], [-0.55, 0.55]]
    grunts = []
    k = 0
    for w, offs in zip(workers, gpos):
        row = []
        for o in offs:
            row.append(Node("grunt", w.pos + np.array([o * s, -1.35 * s, 0]), 0.27 * s, grunt_rings[k]))
            k += 1
        grunts.append(row)
    return orc, rev, workers, grunts


class CompanyV6(Scene):
    def cap(self, key):
        g = VGroup(*[S(l, 72) for l in CAPS[key]]).arrange(DOWN, aligned_edge=LEFT, buff=0.1)
        if g.width > 4.3:
            g.scale_to_fit_width(4.3)
        return g.move_to([-config.frame_width / 2 + EDGE, 0.3, 0], aligned_edge=LEFT)

    def swap(self, old, key, *also, t=0.4):
        """Rest, quick caption replace while nothing moves, read hold, then the beat's motion."""
        new = self.cap(key)
        self.wait(0.4)
        self.play(FadeOut(old), run_time=0.12)
        self.play(FadeIn(new), run_time=0.18)
        self.wait(1.2)
        if also:
            self.play(*also, run_time=t)
        return new

    def flash(self, n, color=None):
        g = n.glow
        if color:
            g.set_stroke(color)
        return Succession(g.animate(run_time=0.15).set_stroke(opacity=0.6),
                          g.animate(run_time=0.3).set_stroke(opacity=0))

    def pulse(self, a, b, color, t=0.45, delay=0.0, mob=None, width=6):
        p0, p1 = ends(a, b)
        dot = (mob or Dot(radius=0.07, color=color)).move_to(p0).set_opacity(0)
        trail = TracedPath(dot.get_center, stroke_color=color, stroke_width=width, dissipating_time=0.3)
        self.add(trail)
        return Succession(Wait(delay), dot.animate(run_time=0.01).set_opacity(1),
                          MoveAlongPath(dot, Line(p0, p1), run_time=t, rate_func=rate_functions.ease_in_out_sine),
                          AnimationGroup(FadeOut(dot, run_time=0.12), self.flash(b)))

    def edges(self, exe, orc, rev, workers, grunts):
        ln = lambda a, b: Line(*ends(a, b), stroke_color=EDGEC, stroke_width=4)
        e = VGroup(ln(exe, orc), ln(exe, rev),
                   DashedLine(*ends(orc, rev), stroke_color=EDGEC, stroke_width=4, dash_length=0.12),
                   *[ln(orc, w) for w in workers], *[ln(w, g) for w, gs in zip(workers, grunts) for g in gs])
        return e

    def construct(self):
        cw = PROVIDER[kind("format")]   # the caught Worker
        cr = PROVIDER[kind("review")]   # the reviewer
        self.add(S(BADGE, 22, "#8d94c0", "MEDIUM").to_corner(UR, buff=0.6).shift(UP * 0.25))

        X = 2.6
        you = VGroup(RoundedRectangle(width=1.2, height=0.56, corner_radius=0.2, fill_color=WHITE,
                                      fill_opacity=1, stroke_width=0), S("you", 28, NAVY)).move_to([X, 3.05, 0])
        you_n = Node("executive", you.get_center(), 0.28, WHITE)  # anchor only
        exe = Node("executive", [X, 1.8, 0], 0.44, cr)
        grings = [FREE, cr, FREE, cw, FREE]
        orc, rev, workers, grunts = team(X - 1.2, 0.35, 1.0, cw, cr, [cr, cw, cr], grings)
        rev.col = cr
        allg = [g for gs in grunts for g in gs]
        e1 = self.edges(exe, orc, rev, workers, grunts)
        e_you = Line(*ends(you_n, exe), stroke_color=EDGEC, stroke_width=4)
        e1.set_stroke(opacity=0.35)
        e_you.set_stroke(opacity=0.35)
        nodes1 = [exe, orc, rev] + workers + allg
        self.add(e_you, e1, *[p for n in nodes1 for p in n.parts()])

        # Labels (rung names) and transient aliases.
        def label(text, n, side):
            return S(text, 26, SOFT, "BOLD").next_to(n.ring, side, buff=0.14)
        L = {"executive": label("Executive", exe, RIGHT), "orchestrator": label("Orchestrator", orc, LEFT),
             "reviewer": label("reviewer", rev, RIGHT), "worker": label("Worker", workers[0], LEFT),
             "grunt": label("Grunt", grunts[0][0], LEFT)}
        A = {}
        for k, lab in L.items():
            A[k] = S(ALIAS[k], 22, AMBER, "SEMIBOLD").next_to(lab, DOWN, aligned_edge=LEFT if k in ("executive", "reviewer") else RIGHT, buff=0.06)
        A["you"] = S(ALIAS["you"], 22, AMBER, "SEMIBOLD").next_to(you, RIGHT, buff=0.2)

        # Beat 1 (0-3 s): the company appears top-down, names with aliases.
        cap = self.cap("hook")
        legend = VGroup(S("providers", 24, WHITE, "BOLD"),
                        *[VGroup(Circle(radius=0.11, stroke_color=c, stroke_width=6), S(n, 24, c, "BOLD")).arrange(RIGHT, buff=0.1)
                          for n, c in LEGEND]).arrange(RIGHT, buff=0.32).move_to([X - 0.3, -3.5, 0])
        rows = [([], [you], ["you"]), ([exe], [], ["executive"]), ([orc, rev], [], ["orchestrator", "reviewer"]),
                (workers, [], ["worker"]), (allg, [], ["grunt"])]
        self.play(FadeIn(cap), run_time=0.25)
        self.wait(1.2)
        self.play(FadeIn(you, shift=DOWN * 0.2), FadeIn(A["you"]), run_time=0.4)
        self.wait(0.2)
        for ns, _, keys in rows[1:]:
            anims = [a for n in ns for a in n.on()] + [FadeIn(L[k], shift=RIGHT * 0.1) for k in keys] + [FadeIn(A[k]) for k in keys]
            self.play(*anims, run_time=0.38)
            self.wait(0.12)
        self.play(e1.animate.set_stroke(opacity=1), e_you.animate.set_stroke(opacity=1), FadeIn(legend, shift=UP * 0.15), run_time=0.35)
        self.wait(0.2)
        # Everything off except you and the Executive.
        rest = [n for n in nodes1 if n is not exe]
        self.play(*[FadeOut(a) for a in A.values()],
                  *[n.img.animate.set_opacity(0.18) for n in rest], *[n.ring.animate.set_stroke(OFF) for n in rest],
                  e1.animate.set_stroke(opacity=0.35), run_time=0.35)

        # Beat 2: you and the Executive talk it through, one turn at a time.
        cap = self.swap(cap, "think")
        bubbles = []
        spots = [(X - 1.75, 2.85), (X + 1.75, 2.95)]
        for i, (w, (bx, by)) in enumerate(zip([0.9, 0.95], spots)):
            left = i % 2 == 0
            b = bubble(w).move_to([bx, by, 0])
            a, z = (you_n, exe) if left else (exe, you_n)
            self.play(GrowFromCenter(b), self.pulse(a, z, WHITE if left else AMBER, 0.32), run_time=0.45,
                      rate_func=rate_functions.ease_out_back)
            self.wait(0.25)
            bubbles.append(b)
        req = card(w=0.6, h=0.42).move_to(exe.pos + LEFT * 1.0)
        self.play(*[b.animate.scale(0.2).move_to(req) for b in bubbles], run_time=0.5)
        self.play(FadeOut(VGroup(*bubbles), run_time=0.1), GrowFromCenter(req), run_time=0.35,
                  rate_func=rate_functions.ease_out_back)

        # Beat 3: plan with the Orchestrator (clarify, analyze), then delegate.
        cap = self.swap(cap, "plan", *orc.on(), req.animate.move_to(orc.pos + LEFT * 0.62 + UP * 0.5),
                        e1[0].animate.set_stroke(opacity=1), t=0.6)
        side = (orc.pos + exe.pos) / 2 + RIGHT * 0.6
        tag1 = S("clarify", 26, AMBER, "BOLD").move_to(side)
        tag2 = S("analyze", 26, AMBER, "BOLD").move_to(side)
        self.play(FadeIn(tag1), run_time=0.15)
        self.wait(0.5)
        self.play(self.pulse(orc, exe, AMBER, 0.45, mob=S("?", 34, AMBER)), run_time=0.6)
        self.play(self.pulse(exe, orc, GREEN, 0.45, mob=S("✓", 30, GREEN)), run_time=0.6)
        self.play(FadeOut(tag1), FadeIn(tag2), run_time=0.15)
        self.wait(0.5)
        self.play(self.pulse(orc, exe, WHITE, 0.45, mob=card(color=WHITE, w=0.34, h=0.24)), run_time=0.6)
        self.play(self.pulse(exe, orc, GREEN, 0.45, mob=S("✓", 30, GREEN)), run_time=0.6)
        self.play(FadeOut(tag2), e1.animate.set_stroke(opacity=1), run_time=0.2)
        cards = [req] + [card(w=0.5, h=0.35).move_to(req) for _ in range(2)]
        self.add(*cards[1:])
        # One branch at a time: card down to a Worker, out to its Grunts, back up.
        steps = []
        for i, (c, w, gs) in enumerate(zip(cards, workers, grunts)):
            d = 0.9 * min(i, 1)
            seq = [Wait(d), AnimationGroup(c.animate(run_time=0.45, rate_func=rate_functions.ease_in_out_cubic).move_to(w.pos + UP * 0.55),
                                           *[a for a in w.on()])]
            steps.append(Succession(*seq))
            for j, g in enumerate(gs):
                steps.append(Succession(Wait(d + 0.45), AnimationGroup(*g.on(), run_time=0.2)))
                steps.append(self.pulse(w, g, WHITE, 0.4, delay=d + 0.5 + 0.1 * j))
                steps.append(self.pulse(g, w, LIME, 0.4, delay=d + 1.15 + 0.1 * j))
        self.play(*steps, run_time=2.25)
        # Results arrive at the Orchestrator one at a time; the script checks each.
        cap = self.swap(cap, "check", *rev.on(), t=0.3)
        ticks = VGroup()
        for i, (c, w) in enumerate(zip(cards, workers)):
            self.play(c.animate.move_to(orc.pos + DOWN * 0.68 + RIGHT * (0.5 * i - 0.5)),
                      self.pulse(w, orc, LIME, 0.3), run_time=0.38)
            t = VGroup(Circle(radius=0.11, fill_color=GREEN, fill_opacity=1, stroke_width=0),
                       S("✓", 16, NAVY)).move_to(c.get_corner(UR))
            ticks.add(t)
            self.play(GrowFromCenter(t), run_time=0.15, rate_func=rate_functions.ease_out_back)
        # The catch: to the reviewer, red, back to its Worker, fixed, back green.
        caught = cards[1]
        self.remove(ticks[1])
        p0, p1 = ends(orc, rev)
        self.play(caught.animate.scale(1.35).move_to(p1 + LEFT * 0.45), run_time=0.6, rate_func=rate_functions.ease_in_out_cubic)
        self.wait(0.2)
        self.play(self.flash(rev), caught[0].animate.set_fill(RED), run_time=0.4)
        trail = TracedPath(caught.get_center, stroke_color=RED, stroke_width=10, dissipating_time=0.5)
        self.add(trail)
        self.play(caught.animate(rate_func=rate_functions.ease_in_out_cubic).move_to(workers[1].pos + UP * 0.6), run_time=0.7)
        self.play(self.flash(workers[1], RED), run_time=0.5)
        self.play(caught[0].animate.set_fill(GREEN), self.flash(workers[1], GREEN), run_time=0.55)
        trail.set_stroke(GREEN)
        self.play(caught.animate(rate_func=rate_functions.ease_in_out_cubic).move_to(p1 + LEFT * 0.45), run_time=0.75)
        self.play(self.flash(rev, GREEN), caught.animate.scale(1 / 1.35).move_to(orc.pos + DOWN * 0.68), run_time=0.5)
        t = VGroup(Circle(radius=0.11, fill_color=GREEN, fill_opacity=1, stroke_width=0),
                   S("✓", 16, NAVY)).move_to(caught.get_corner(UR))
        self.play(GrowFromCenter(t), run_time=0.3, rate_func=rate_functions.ease_out_back)
        ticks.add(t)
        self.remove(trail)

        # Beat 4: a second project under the same Executive.
        e_top = VGroup(e1[0], e1[1])
        n1 = [orc, rev] + workers + allg
        labs1 = [L[k] for k in ("orchestrator", "reviewer", "worker", "grunt")]
        team1 = Group(*e1[2:], *[p for n in n1 for p in n.parts()], *labs1)
        self.play(FadeOut(VGroup(*cards, ticks)), run_time=0.2)
        cap = self.swap(cap, "many", team1.animate.scale(0.55, about_point=np.array([X, 1.25, 0])).shift(LEFT * 1.55),
                        t=0.7)
        self.play(*[n.img.animate.set_opacity(0.35) for n in n1], *[n.ring.animate.set_stroke(opacity=0.35) for n in n1],
                  *[l.animate.set_opacity(0.35) for l in labs1], *[e.animate.set_stroke(opacity=0.35) for e in e1[2:]],
                  e_top[0].animate.put_start_and_end_on(*ends(exe, orc)).set_stroke(opacity=0.5),
                  e_top[1].animate.put_start_and_end_on(*ends(exe, rev)).set_stroke(opacity=0.5), run_time=0.5)
        orc2, rev2, workers2, grunts2 = team(X + 1.25, -0.1, 0.55, cw, cr, [cw, cr, cw], [cr, FREE, cw, FREE, cr])
        allg2 = [g for gs in grunts2 for g in gs]
        e2 = self.edges(exe, orc2, rev2, workers2, grunts2)
        for n in [orc2, rev2] + workers2 + allg2:
            n.img.set_opacity(1)
            n.ring.set_stroke(n.col, opacity=1)
        team2 = Group(e2, *[p for n in [orc2, rev2] + workers2 + allg2 for p in n.parts()])
        self.play(FadeIn(team2, scale=0.6, shift=DOWN * 0.3), run_time=0.8, rate_func=rate_functions.ease_out_cubic)
        flat2 = [(w, g) for w, gs in zip(workers2, grunts2) for g in gs]
        busy = [self.pulse(exe, orc2, WHITE, 0.45, 0.0),
                self.pulse(orc2, exe, AMBER, 0.4, 0.45, mob=S("?", 26, AMBER)), self.pulse(exe, orc2, GREEN, 0.4, 0.85, mob=S("✓", 22, GREEN)),
                self.pulse(exe, orc, WHITE, 0.45, 1.0), self.pulse(orc, exe, LIME, 0.45, 1.6)]
        busy += [self.pulse(orc2, w, WHITE, 0.4, 1.20 + 0.15 * i) for i, w in enumerate(workers2)]
        busy += [self.pulse(w, g, WHITE, 0.35, 1.50 + 0.1 * i) for i, (w, g) in enumerate(flat2)]
        busy += [self.pulse(g, w, LIME, 0.35, 1.95 + 0.1 * i) for i, (w, g) in enumerate(flat2)]
        busy += [self.pulse(orc, w, WHITE, 0.35, 1.35 + 0.25 * i, width=4) for i, w in enumerate(workers)]
        self.play(*busy, run_time=2.25)

        # Beat 5: close. The trees and legend fade out entirely.
        live = [m for m in self.mobjects if not (isinstance(m, Text) and m.text == BADGE)]
        self.play(*[FadeOut(m) for m in live], run_time=0.4)
        head = VGroup(*[S(l, 64) for l in TAG]).arrange(DOWN, buff=0.1)
        wm = Text(WORDMARK, font=SANS, font_size=140, color=BLUE, weight="HEAVY")
        mat = S(MATURITY, 30, "#7d84b0", "MEDIUM")
        link = Text(LINK, font=SANS, font_size=40, color=WHITE, weight="SEMIBOLD")
        block = VGroup(wm, mat, link).arrange(DOWN, buff=0.28)
        mat.shift(UP * 0.12)
        if block.width > 12.4:
            block.scale_to_fit_width(12.4)
        block.move_to(ORIGIN)
        self.play(FadeIn(wm, scale=0.85), FadeIn(mat), run_time=0.35, rate_func=rate_functions.ease_out_back)
        self.play(FadeIn(link, shift=UP * 0.15), run_time=0.4)
        self.wait(3.9)
