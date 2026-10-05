"""
Canyon Endurace CF SLX 7 AXS (Crystal White) - parametric Blender model.

Built from Canyon's published geometry table. All dimensions in mm.
Coordinates: +X forward, +Z up, +Y = rider's left (drive side is -Y). BB at origin.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python build_endurace.py -- --size S --render
Or open Blender > Scripting tab > open this file > Run Script.
"""
import bpy, bmesh, math, os, sys
from mathutils import Euler, Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SIZE = argv[argv.index("--size") + 1] if "--size" in argv else "S"
RENDER = "--render" in argv
OUT = os.path.dirname(os.path.abspath(__file__))

# size: stack, reach, seat tube, seat angle, head angle, head tube, wheelbase
GEOM = {
    "2XS": (524, 378, 432, 73.5, 70.3, 103, 999),
    "XS":  (545, 383, 462, 73.5, 71.0, 123, 1005),
    "S":   (565, 386, 492, 73.5, 71.8, 141, 1008),
    "M":   (586, 388, 522, 73.5, 72.5, 161, 1009),
    "L":   (608, 397, 552, 73.5, 72.5, 183, 1025),
    "XL":  (633, 405, 582, 73.5, 72.8, 208, 1039),
    "2XL": (652, 415, 612, 73.5, 72.8, 229, 1054),
}
CHAINSTAY, BB_DROP = 418, 74
TIRE_W = 32                       # Schwalbe Pro One 32mm
R_BEAD = 311                      # 622 ISO / 2
R_TIRE = R_BEAD + TIRE_W          # outer radius
SADDLE_HEIGHT = 720               # BB to saddle top along seat axis
S = 0.001                         # mm -> m

STACK, REACH, ST_LEN, STA, HTA, HT_LEN, WB = GEOM[SIZE]
CRANK_LENGTH = {"2XS": 160, "XS": 160, "S": 165, "M": 165, "L": 170, "XL": 170, "2XL": 170}[SIZE]
# The owner's size-S build uses an 80 mm stem, overriding the stock 90 mm specification.
STEM_LENGTH = {"2XS": 70, "XS": 80, "S": 80, "M": 100, "L": 110, "XL": 120, "2XL": 130}[SIZE]
sta, hta = math.radians(STA), math.radians(HTA)

def v(x, y, z):
    return Vector((x, y, z))

# ---------------------------------------------------------------- scene setup
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

ROOT = bpy.data.objects.new(f"Endurace_CF_SLX_7_AXS_{SIZE}", None)
ROOT["frameSize"] = SIZE
scene.collection.objects.link(ROOT)

def add(ob, m=None):
    if ob.name not in scene.collection.objects:
        scene.collection.objects.link(ob)
    if m is not None:
        ob.data.materials.clear()
        ob.data.materials.append(m)
    ob.parent = ROOT
    return ob

def mat(name, color, rough=0.5, metal=0.0, coat=0.0):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if coat and "Coat Weight" in b.inputs:
        b.inputs["Coat Weight"].default_value = coat
    m.diffuse_color = (*color, 1)
    return m

WHITE  = mat("Crystal White", (0.88, 0.88, 0.86), rough=0.3, coat=1.0)
CARBON = mat("Carbon Black", (0.02, 0.02, 0.022), rough=0.35, coat=0.5)
CARBON_WEAVE = mat("Carbon Weave", (0.02, 0.02, 0.022), rough=0.22, coat=1.0)
_nt = CARBON_WEAVE.node_tree
_tc, _ck = _nt.nodes.new("ShaderNodeTexCoord"), _nt.nodes.new("ShaderNodeTexChecker")
_ck.inputs["Scale"].default_value = 700                     # fine 3K weave (object coords in m)
_ck.inputs["Color1"].default_value = (0.013, 0.013, 0.014, 1)
_ck.inputs["Color2"].default_value = (0.022, 0.022, 0.024, 1)
_nt.links.new(_tc.outputs["Object"], _ck.inputs["Vector"])
_nt.links.new(_ck.outputs["Color"], _nt.nodes.get("Principled BSDF").inputs["Base Color"])
TIRE   = mat("Tire Rubber", (0.015, 0.015, 0.015), rough=0.75)

def tread_bump(m, r_tread=0.336, slick=0.0035, edge=0.012, ridges=860, slope=2500):
    """Schwalbe Pro One Evo tread on a wheel-centred torus (object coords, metres):
    slick centre strip |z| < slick, chevron micro-ridges on the shoulders out to |z| < edge."""
    nt = m.node_tree
    N, Lk = nt.nodes, nt.links
    tc, sep = N.new("ShaderNodeTexCoord"), N.new("ShaderNodeSeparateXYZ")
    Lk.new(tc.outputs["Object"], sep.inputs[0])
    def op(kind, a, b=None):
        n = N.new("ShaderNodeMath")
        n.operation = kind
        for i, val in enumerate((a, b)):
            if val is None:
                continue
            if isinstance(val, (int, float)):
                n.inputs[i].default_value = val
            else:
                Lk.new(val, n.inputs[i])
        return n.outputs[0]
    x, y, z = sep.outputs[0], sep.outputs[1], sep.outputs[2]
    theta = op("ARCTAN2", y, x)
    r = op("SQRT", op("ADD", op("MULTIPLY", x, x), op("MULTIPLY", y, y)))
    az = op("ABSOLUTE", z)
    wave = op("SINE", op("ADD", op("MULTIPLY", theta, ridges), op("MULTIPLY", az, slope)))
    mask = op("MULTIPLY", op("MULTIPLY", op("GREATER_THAN", az, slick), op("LESS_THAN", az, edge)),
              op("GREATER_THAN", r, r_tread))
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = 0.0002
    Lk.new(op("MULTIPLY", wave, mask), bump.inputs["Height"])
    Lk.new(bump.outputs["Normal"], N.get("Principled BSDF").inputs["Normal"])

tread_bump(TIRE)
TAPE   = mat("Bar Tape", (0.012, 0.012, 0.012), rough=0.75)
_tn = TAPE.node_tree
_tuv, _tsep = _tn.nodes.new("ShaderNodeTexCoord"), _tn.nodes.new("ShaderNodeSeparateXYZ")
_tn.links.new(_tuv.outputs["UV"], _tsep.inputs[0])
_tph = _tn.nodes.new("ShaderNodeMath"); _tph.operation = "MULTIPLY_ADD"     # u*100mm/25mm pitch + v
_tph.inputs[1].default_value = 100.0 / 25.0
_tn.links.new(_tsep.outputs["X"], _tph.inputs[0])
_tn.links.new(_tsep.outputs["Y"], _tph.inputs[2])
_tfr = _tn.nodes.new("ShaderNodeMath"); _tfr.operation = "FRACT"              # sawtooth = overlapping wraps
_tn.links.new(_tph.outputs[0], _tfr.inputs[0])
_tpow = _tn.nodes.new("ShaderNodeMath"); _tpow.operation = "POWER"          # steep rise = visible overlap edge
_tpow.inputs[1].default_value = 6.0
_tn.links.new(_tfr.outputs[0], _tpow.inputs[0])
_tbump = _tn.nodes.new("ShaderNodeBump")
_tbump.inputs["Strength"].default_value = 1.0
_tbump.inputs["Distance"].default_value = 0.0008
_tn.links.new(_tpow.outputs[0], _tbump.inputs["Height"])
_tramp = _tn.nodes.new("ShaderNodeValToRGB")                                 # each wrap slightly shaded
_tramp.color_ramp.elements[0].color = (0.007, 0.007, 0.007, 1)
_tramp.color_ramp.elements[1].color = (0.02, 0.02, 0.02, 1)
_tn.links.new(_tfr.outputs[0], _tramp.inputs["Fac"])
_tn.links.new(_tramp.outputs["Color"], _tn.nodes.get("Principled BSDF").inputs["Base Color"])
_tn.links.new(_tbump.outputs["Normal"], _tn.nodes.get("Principled BSDF").inputs["Normal"])
FINISH_TAPE = mat("Finishing Tape", (0.008, 0.008, 0.008), rough=0.25)
HOOD_RUBBER = mat("Hood Rubber", (0.015, 0.015, 0.016), rough=0.7)
_hn, _hl = HOOD_RUBBER.node_tree.nodes, HOOD_RUBBER.node_tree.links
def _hop(kind, a_, b_=None):
    n_ = _hn.new("ShaderNodeMath")
    n_.operation = kind
    for i_, val in enumerate((a_, b_)):
        if val is None:
            continue
        if isinstance(val, (int, float)):
            n_.inputs[i_].default_value = val
        else:
            _hl.new(val, n_.inputs[i_])
    return n_.outputs[0]
_htc, _hsep = _hn.new("ShaderNodeTexCoord"), _hn.new("ShaderNodeSeparateXYZ")
_hl.new(_htc.outputs["Object"], _hsep.inputs[0])
_hx, _hy = _hsep.outputs[0], _hsep.outputs[1]
_chev = _hop("SINE", _hop("ADD", _hop("MULTIPLY", _hx, 1000.0), _hop("MULTIPLY", _hop("ABSOLUTE", _hy), 1000.0)))
_dash = _hop("SINE", _hop("MULTIPLY", _hy, 700.0))
_hh = _hop("MULTIPLY", _hop("MAXIMUM", _hop("SUBTRACT", _chev, 0.6), 0.0), _hop("MAXIMUM", _dash, 0.0))
_hb = _hn.new("ShaderNodeBump")
_hb.inputs["Strength"].default_value = 0.6
_hb.inputs["Distance"].default_value = 0.0008
_hl.new(_hh, _hb.inputs["Height"])
_hl.new(_hb.outputs["Normal"], _hn.get("Principled BSDF").inputs["Normal"])
LEVER_GLOSS = mat("Rival Lever Gloss", (0.035, 0.035, 0.04), rough=0.12, metal=0.3, coat=1.0)
PADDLE_BLACK = mat("Shift Paddle", (0.012, 0.012, 0.013), rough=0.55)
METAL  = mat("Steel", (0.6, 0.6, 0.62), rough=0.25, metal=1.0)
DARK   = mat("Dark Metal", (0.08, 0.08, 0.09), rough=0.35, metal=1.0)
LOGO   = mat("Logo Black", (0.01, 0.01, 0.01), rough=0.3)
AXS_GREY = mat("AXS Grey", (0.16, 0.16, 0.17), rough=0.4, metal=0.3)
PRINT_GREY = mat("Print Grey", (0.42, 0.42, 0.44), rough=0.5)

# ---------------------------------------------------------------- helpers
def tube(name, pts, r, m, smooth=False, cyclic=False):
    """Swept round tube along points. r = radius or list of per-point radii (mm)."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.resolution_u = 24
    cu.bevel_resolution = 6
    cu.use_fill_caps = True
    radii = r if isinstance(r, (list, tuple)) else [r] * len(pts)
    cu.bevel_depth = S
    if smooth:
        sp = cu.splines.new("BEZIER")
        sp.bezier_points.add(len(pts) - 1)
        for bp, p, rad in zip(sp.bezier_points, pts, radii):
            bp.co = Vector(p) * S
            bp.handle_left_type = bp.handle_right_type = "AUTO"
            bp.radius = rad
    else:
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        for pt, p, rad in zip(sp.points, pts, radii):
            pt.co = (*(Vector(p) * S), 1)
            pt.radius = rad
    sp.use_cyclic_u = cyclic
    return add(bpy.data.objects.new(name, cu), m)

def smooth_shade(ob):
    for p in ob.data.polygons:
        p.use_smooth = True

def cyl(name, c, r, depth, m, axis="Y", verts=64):
    rot = {"Y": (math.pi / 2, 0, 0), "X": (0, math.pi / 2, 0), "Z": (0, 0, 0)}[axis]
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r * S, depth=depth * S,
                                        location=Vector(c) * S, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    return add(ob, m)

def torus(name, c, major, minor, m, lateral_scale=1.0):
    """Torus standing in the XZ plane (wheel plane)."""
    bpy.ops.mesh.primitive_torus_add(major_radius=major * S, minor_radius=minor * S,
                                     major_segments=128, minor_segments=24,
                                     location=Vector(c) * S, rotation=(math.pi / 2, 0, 0))
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (1, 1, lateral_scale)
    smooth_shade(ob)
    return add(ob, m)

def box(name, c, size, m, rot=(0, 0, 0), bevel=3):
    bpy.ops.mesh.primitive_cube_add(size=1, location=Vector(c) * S, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = Vector(size) * S
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    mod = ob.modifiers.new("bevel", "BEVEL")
    mod.width = bevel * S
    mod.segments = 4
    smooth_shade(ob)
    return add(ob, m)

def loft(name, sections, m, n=24, exp=(0.7, 0.9), subsurf=True):
    """Closed lofted body. sections: (x, half_width, half_height, z_center) in local mm."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rings = []
    for x, hw, hh, zc in sections:
        ring = []
        for j in range(n):
            a = 2 * math.pi * j / n
            c, s = math.cos(a), math.sin(a)
            y = hw * math.copysign(abs(c) ** exp[0], c)
            z = zc + hh * math.copysign(abs(s) ** exp[1], s)
            ring.append(bm.verts.new((x * S, y * S, z * S)))
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        for j in range(n):
            bm.faces.new((r0[j], r0[(j + 1) % n], r1[(j + 1) % n], r1[j]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    ob = add(bpy.data.objects.new(name, me), m)
    smooth_shade(ob)
    if subsurf:
        mod = ob.modifiers.new("subsurf", "SUBSURF")
        mod.levels = mod.render_levels = 2
    return ob

def ribbon(name, pts, width, thick, m, normal_fn, closed=False):
    """Flat strap with a width x thick rectangular section swept along pts (mm).
    normal_fn(p, tangent) gives the thickness direction at each point."""
    bm = bmesh.new()
    n = len(pts)
    rings = []
    for i, p in enumerate(pts):
        nxt = pts[(i + 1) % n] if closed else pts[min(i + 1, n - 1)]
        prv = pts[i - 1] if closed else pts[max(i - 1, 0)]
        tng = (nxt - prv).normalized()
        nv = normal_fn(p, tng)
        nv = (nv - tng * nv.dot(tng)).normalized()
        w = tng.cross(nv)
        wi = width[i] if isinstance(width, (list, tuple)) else width
        ti = thick[i] if isinstance(thick, (list, tuple)) else thick
        rings.append([bm.verts.new((p + w * (sw * wi / 2) + nv * (st * ti / 2)) * S)
                      for sw, st in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    for i in range(n if closed else n - 1):
        r0, r1 = rings[i], rings[(i + 1) % n]
        for k in range(4):
            bm.faces.new((r0[k], r0[(k + 1) % 4], r1[(k + 1) % 4], r1[k]))
    if not closed:
        bm.faces.new(rings[0][::-1])
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = add(bpy.data.objects.new(name, me), m)
    smooth_shade(ob)
    es = ob.modifiers.new("edges", "EDGE_SPLIT")
    es.split_angle = math.radians(50)
    return ob

def catmull(ctrl, n):
    """Catmull-Rom through control points (tuples of any length); returns n+1 samples."""
    P = [ctrl[0]] + list(ctrl) + [ctrl[-1]]
    out = []
    for k in range(n + 1):
        t = k / n * (len(ctrl) - 1)
        i = min(int(t), len(ctrl) - 2)
        u = t - i
        p0, p1, p2, p3 = P[i], P[i + 1], P[i + 2], P[i + 3]
        out.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * u + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * u * u +
                                (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * u ** 3) for j in range(len(p1))))
    return out

def sweep(name, pts, chord, thick, m, up0=None, n=24, uv_len=100.0):
    """Tube with an oval cross-section (chord x thick, per point, mm) swept along pts, using a
    rotation-minimising frame so it never twists. UV: u = arc length / uv_len, v = around."""
    up = up0 if up0 is not None else v(0, 0, 1)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    rings, arc, N = [], [0.0], len(pts)
    for i in range(1, N):
        arc.append(arc[-1] + (pts[i] - pts[i - 1]).length)
    for i, p in enumerate(pts):
        tng = (pts[min(i + 1, N - 1)] - pts[max(i - 1, 0)]).normalized()
        up = (up - tng * up.dot(tng)).normalized()
        side = tng.cross(up)
        rings.append([bm.verts.new((p + side * (math.cos(2 * math.pi * k / n) * chord[i] / 2) +
                                    up * (math.sin(2 * math.pi * k / n) * thick[i] / 2)) * S) for k in range(n)])
    for i in range(N - 1):
        for k in range(n):
            f = bm.faces.new((rings[i][k], rings[i][(k + 1) % n], rings[i + 1][(k + 1) % n], rings[i + 1][k]))
            for lp, (ii, kk) in zip(f.loops, ((i, k), (i, k + 1), (i + 1, k + 1), (i + 1, k))):
                lp[uvl].uv = (arc[ii] / uv_len, kk / n)
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = add(bpy.data.objects.new(name, me), m)
    smooth_shade(ob)
    return ob

# ---------------------------------------------------------------- profile / sprocket helpers
from mathutils.geometry import tessellate_polygon

PITCH = 12.7                                               # chain pitch (mm)

def pitch_r(n):
    return PITCH / (2 * math.sin(math.pi / n))

def circle_loop(r, n=48, cx=0.0, cz=0.0):
    return [(cx + r * math.cos(2 * math.pi * k / n), cz + r * math.sin(2 * math.pi * k / n)) for k in range(n)]

def window_loop(r0, r1, a0, a1, n=10):
    """Annular-sector window between radii r0..r1 and angles a0..a1 (radians)."""
    outer = [(r1 * math.cos(a0 + (a1 - a0) * k / n), r1 * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]
    inner = [(r0 * math.cos(a1 - (a1 - a0) * k / n), r0 * math.sin(a1 - (a1 - a0) * k / n)) for k in range(n + 1)]
    return outer + inner

def sprocket_loop(n, tip=3.4, seat=3.95, seat_steps=6):
    """Tooth outline (x, z) of an n-tooth sprocket: half-circle roller seats on the pitch circle,
    flanks rising to a rounded tip between seats."""
    R, half, pts = pitch_r(n), math.pi / n, []
    for k in range(n):
        th = 2 * math.pi * k / n
        cx, cz = R * math.cos(th), R * math.sin(th)
        for j in range(seat_steps + 1):
            psi = th - math.pi / 2 - math.pi * j / seat_steps
            pts.append((cx + seat * math.cos(psi), cz + seat * math.sin(psi)))
        for f in (-0.18, 0.18):
            ta = th + half + f * half
            pts.append(((R + tip) * math.cos(ta), (R + tip) * math.sin(ta)))
    return pts

def extrude_profile(name, loops, y0, thick, m, origin=None, axes=None):
    """Extrude 2D loops (first = outline, rest = holes; (u, w) in mm) by `thick` along the normal.
    Default plane: u -> X, w -> Z, normal -> Y (the wheel plane). axes = (U, W, N) overrides."""
    origin = origin if origin is not None else v(0, 0, 0)
    U, W, N = axes if axes else (v(1, 0, 0), v(0, 0, 1), v(0, 1, 0))
    tris = tessellate_polygon([[Vector((u, w, 0.0)) for u, w in loop] for loop in loops])
    flat = [pt for loop in loops for pt in loop]
    bm = bmesh.new()
    front = [bm.verts.new((origin + U * u + W * w + N * y0) * S) for u, w in flat]
    back = [bm.verts.new((origin + U * u + W * w + N * (y0 + thick)) * S) for u, w in flat]
    for a, b, c in tris:
        for face in ((front[a], front[b], front[c]), (back[c], back[b], back[a])):
            try:
                bm.faces.new(face)
            except ValueError:
                pass
    i0 = 0
    for loop in loops:
        for k in range(len(loop)):
            a, b = i0 + k, i0 + (k + 1) % len(loop)
            try:
                bm.faces.new((front[a], front[b], back[b], back[a]))
            except ValueError:
                pass
        i0 += len(loop)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return add(bpy.data.objects.new(name, me), m)

def along(u):
    """Euler rotation that points local +X along the in-plane direction u."""
    return (0, -math.atan2(u.z, u.x), 0)

# ---------------------------------------------------------------- decals
FONT_DIR = "/System/Library/Fonts/Supplemental/"

def font(fname):
    path = os.path.join(FONT_DIR, fname)
    return bpy.data.fonts.load(path, check_existing=True) if os.path.exists(path) else None

FONT_HEAVY = font("Arial Black.ttf")
FONT_COND = font("DIN Condensed Bold.ttf")
FONT_BOLD = font("Arial Bold.ttf")
FONT_ROUNDED = font("Arial Rounded Bold.ttf")

def text_bmesh(text, fnt, width, height, cuts):
    """Flat text as a dense triangle mesh, centred and scaled to width x height (mm)."""
    cu = bpy.data.curves.new("tmp_text", "FONT")
    cu.body = text
    if fnt:
        cu.font = fnt
    tmp = bpy.data.objects.new("tmp_text", cu)
    scene.collection.objects.link(tmp)
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(tmp)
    bpy.data.curves.remove(cu)
    bm = bmesh.new()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    xs = [p.co.x for p in bm.verts]
    ys = [p.co.y for p in bm.verts]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    sx, sy = width / (max(xs) - min(xs)), height / (max(ys) - min(ys))
    for p in bm.verts:
        p.co = Vector(((p.co.x - cx) * sx, (p.co.y - cy) * sy, 0))
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    return bm

def rect_bmesh(width, height, nx=24, ny=8):
    """Dense flat rectangle centred at the origin (mm)."""
    bm = bmesh.new()
    grid = [[bm.verts.new(((i / nx - 0.5) * width, (j / ny - 0.5) * height, 0)) for i in range(nx + 1)]
            for j in range(ny + 1)]
    for j in range(ny):
        for i in range(nx):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    return bm

def disc_bmesh(radius, n=24):
    bm = bmesh.new()
    c0 = bm.verts.new((0, 0, 0))
    ring = [bm.verts.new((radius * math.cos(2 * math.pi * k / n), radius * math.sin(2 * math.pi * k / n), 0))
            for k in range(n)]
    for k in range(n):
        bm.faces.new((c0, ring[k], ring[(k + 1) % n]))
    return bm

def shapes_bmesh(polys, cuts=4):
    """Convex 2D polygons (mm) -> one dense flat mesh."""
    bm = bmesh.new()
    for poly in polys:
        bm.faces.new([bm.verts.new((x, y, 0)) for x, y in poly])
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    return bm

def shifted(mapfn, ox, oy):
    return lambda x, y: mapfn(x + ox, y + oy)

def decal(name, text, fnt, width, height, mapfn, m, cuts=4):
    """Text decal whose local (x, y) mm coords are wrapped onto a surface by mapfn."""
    return place(name, text_bmesh(text, fnt, width, height, cuts), mapfn, m)

def place(name, bm, mapfn, m, uv=None):
    """Wrap a flat bmesh (local x, y in mm) onto a surface via mapfn.
    uv=(w, h) maps the centred w x h rectangle to the 0..1 texture square."""
    if uv:
        layer = bm.loops.layers.uv.new("UVMap")
        for f in bm.faces:
            for lp in f.loops:
                lp[layer].uv = (lp.vert.co.x / uv[0] + 0.5, lp.vert.co.y / uv[1] + 0.5)
    for p in bm.verts:
        p.co = mapfn(p.co.x, p.co.y) * S
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = add(bpy.data.objects.new(name, me), m)
    smooth_shade(ob)
    return ob

def glyph_decal(name, json_file, height_mm, mapfn, m):
    """Decal from traced vector outlines (extract_canyon_logo.py): loops in units of text height, tube frame.
    Outer loops and their holes (letter counters) are tessellated together; the mesh is centred on (0, 0)."""
    import json
    from mathutils.geometry import intersect_point_tri_2d
    with open(os.path.join(OUT, json_file)) as f:
        g = json.load(f)
    loops = [[(x * height_mm, y * height_mm) for x, y in lp] for lp in g["loops"] if len(lp) >= 3]
    xs = [p[0] for lp in loops for p in lp]
    ys = [p[1] for lp in loops for p in lp]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    loops = [[(x - cx, y - cy) for x, y in lp] for lp in loops]
    def sarea(lp):
        return 0.5 * sum(lp[i][0] * lp[i - 1][1] - lp[i - 1][0] * lp[i][1] for i in range(len(lp)))
    outer_sign = math.copysign(1, sarea(max(loops, key=lambda l: abs(sarea(l)))))
    outers = [lp for lp in loops if math.copysign(1, sarea(lp)) == outer_sign]
    holes = [lp for lp in loops if math.copysign(1, sarea(lp)) != outer_sign]
    def inside(pt, lp):
        x, y, c = pt[0], pt[1], False
        for i in range(len(lp)):
            (x1, y1), (x2, y2) = lp[i - 1], lp[i]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                c = not c
        return c
    bm = bmesh.new()
    for o in outers:
        group = [o] + [hl for hl in holes if inside(hl[0], o)]
        flat = [p for lp in group for p in lp]
        verts = [bm.verts.new((x, y, 0)) for x, y in flat]
        for tri in tessellate_polygon([[Vector((x, y, 0)) for x, y in lp] for lp in group]):
            try:
                bm.faces.new([verts[i] for i in tri])
            except ValueError:
                pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-4)
    bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if e.calc_length() > 2.0], cuts=1, use_grid_fill=True)
    return place(name, bm, mapfn, m)

def canyon_wordmark(name, side, mapfn, y_extent=44.0):
    """CANYON down-tube decal from canyon_glyphs.json (vectorized from the owner's photo IMG_6968 by
    extract_canyon_logo.py). Glyphs are upright (u reading, v letter-up); on the bike the letter-up
    direction is level/rearward, so the text is sheared onto the tube at the tube's own angle."""
    import json
    with open(os.path.join(OUT, "canyon_glyphs.json")) as f:
        g = json.load(f)
    th = math.atan2(dt_b.z - dt_a.z, dt_b.x - dt_a.x)          # down-tube angle in the side view
    k = y_extent / (g["height"] * math.sin(th))                  # mm per glyph unit
    sgn = -1 if side < 0 else 1                                  # rearward is -x (drive) / +x (non-drive) locally
    def shear(u, v_):
        return u * k + sgn * v_ * k * math.cos(th), v_ * k * math.sin(th)
    loops = [[shear(u, v_) for u, v_ in lp] for lp in g["loops"]]
    xs = [p[0] for lp in loops for p in lp]
    ys = [p[1] for lp in loops for p in lp]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    bm = bmesh.new()
    for lp in loops:
        if len(lp) < 3:
            continue
        verts = [bm.verts.new((x - cx, y - cy, 0)) for x, y in lp]
        for tri in tessellate_polygon([[Vector((x - cx, y - cy, 0)) for x, y in lp]]):
            try:
                bm.faces.new([verts[i] for i in tri])
            except ValueError:
                pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-4)
    bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if e.calc_length() > 3.0], cuts=2, use_grid_fill=True)
    return place(name, bm, mapfn, LOGO)

def tube_map(a, b, ra, rb, side, s_frac, lift=0.4, knots=None):
    """Wrap onto a straight tube a->b; text reads left-to-right as seen from that side. Radius tapers
    ra -> rb, or follows knots [(fraction of length, radius), ...] when given (flared tubes)."""
    u = (b - a).normalized()
    length = (b - a).length
    up = v(-u.z, 0, u.x)
    def radius(s_):
        if not knots:
            return ra + (rb - ra) * s_ / length
        f_ = min(max(s_ / length, 0.0), 1.0)
        for (f0, r0), (f1, r1) in zip(knots, knots[1:]):
            if f_ <= f1:
                return r0 + (r1 - r0) * (f_ - f0) / (f1 - f0)
        return knots[-1][1]
    def f(x, y):
        s_ = s_frac * length + (x if side < 0 else -x)
        r_ = radius(s_)
        return a + u * s_ + up * y + v(0, side * (math.sqrt(max(r_ * r_ - y * y, 0)) + lift), 0)
    return f

def ring_map(c, side, theta0, r_mid, lateral, lift=0.4):
    """Wrap around a wheel: x follows the circumference, y points outward."""
    def f(x, y):
        r_ = r_mid + y
        th = theta0 + x / r_mid * (1 if side > 0 else -1)
        return c + v(r_ * math.cos(th), side * (lateral(r_) + lift), r_ * math.sin(th))
    return f

DECAL_GREY = mat("Sidewall Print", (0.5, 0.5, 0.5), rough=0.6)

# ---------------------------------------------------------------- key points
st_dir = v(-math.cos(sta), 0, math.sin(sta))          # BB -> seat cluster
hd = v(math.cos(hta), 0, -math.sin(hta))              # down the steering axis
hn = v(math.sin(hta), 0, math.cos(hta))               # perpendicular, forward
st_top = st_dir * ST_LEN
ht_top = v(REACH, 0, STACK)
ht_bot = ht_top + hd * HT_LEN
rear = v(-math.sqrt(CHAINSTAY ** 2 - BB_DROP ** 2), 0, BB_DROP)
front = v(rear.x + WB, 0, BB_DROP)
ground_z = BB_DROP - R_TIRE

# ---------------------------------------------------------------- frame
HT_START, HT_L = ht_top - hd * 6, HT_LEN + 10

def ht_profile(t):
    """Head tube (lateral half-width, fore-aft half-depth) at t mm down the steering axis:
    hourglass seen from the front (narrow waist), flaring into the lower bearing."""
    keys = [(0.0, 21, 24), (0.3, 19, 23), (0.5, 19, 23.5), (0.7, 23.5, 26), (0.85, 27.5, 28.5), (1.0, 29.5, 31)]
    f = min(max(t / HT_L, 0.0), 1.0)
    for (f0, w0, h0), (f1, w1, h1) in zip(keys, keys[1:]):
        if f <= f1:
            k = (f - f0) / (f1 - f0)
            k = k * k * (3 - 2 * k)                             # smoothstep: no creases between keys
            return w0 + (w1 - w0) * k, h0 + (h1 - h0) * k

head_tube = loft("head_tube", [(HT_L * k / 40, *ht_profile(HT_L * k / 40), 0) for k in range(41)],
                 WHITE, n=48, exp=(1, 1), subsurf=False)
head_tube.location = HT_START * S
head_tube.rotation_euler = along(hd)

def ht_front_map(t_c, lift):
    """Logo coords (u right as seen from the front, w up) -> head tube front surface."""
    def f(u, w):
        t = t_c - w
        hw, hh = ht_profile(t)
        return HT_START + hd * t + v(0, u, 0) + hn * (hh * math.sqrt(max(1 - (u / hw) ** 2, 0)) + lift)
    return f

LOGO_W, LOGO_H = 36, 22.4
def logo_poly(pts):
    return [((u - 0.5) * LOGO_W, (w - 0.5) * LOGO_H) for u, w in pts]
place("canyon_headtube_logo", shapes_bmesh([
    logo_poly([(0, 0), (0.763, 0), (0.447, 1), (0.246, 1)]),          # big "mountain"
    logo_poly([(0.807, 0), (1, 0), (0.693, 0.732), (0.596, 0.732)]),  # small peak
], cuts=7), ht_front_map(HT_L * 0.72, 0.6), LOGO)
# The top tube's upper surface runs flush into the seat-cluster top; that "frame line" also sets
# the cut of the seat tube top, the seatpost collar and the name tag (all parallel, per owner photo).
P_TOP = st_dir * ST_LEN                                    # seat tube top, on its axis
tt_b = ht_top + hd * 22
_u0 = (tt_b - st_dir * (ST_LEN * 0.9)).normalized()
_n0 = v(-_u0.z, 0, _u0.x)
tt_a = st_dir * ((P_TOP.dot(_n0) - 15) / st_dir.dot(_n0))  # top tube top flush with P_TOP
tt_u = (tt_b - tt_a).normalized()                          # frame line direction (forward, rising)
FRAME_N = v(-tt_u.z, 0, tt_u.x)                            # frame line "up" normal

def cut_to_plane(ob, x_min, p0, n, offset=0.0, x_max=1e9):
    """Slide loft vertices with local x >= x_min (mm) along the loft axis so they land on the world
    plane (p0, n), plus offset (mm) along the axis. Loft axis = local X; object rotation only."""
    R = Euler(ob.rotation_euler).to_matrix()
    p0l, nl = R.transposed() @ (p0 * S), R.transposed() @ n
    for vt in ob.data.vertices:
        if x_min * S - 1e-6 <= vt.co.x <= x_max * S + 1e-6:
            co = vt.co.copy()
            co.x += -(co - p0l).dot(nl) / nl.x + offset * S
            vt.co = co

_tt_len = (tt_b - tt_a).length
TT_KNOTS = [(0.0, 15), (1 - 60 / _tt_len, 17.5), (1.0, 20)]
tube("top_tube", [tt_a, tt_b - tt_u * 60], [15, 17.5], WHITE)
tube("top_tube_stub", [tt_b - tt_u * 78, tt_b - tt_u * 60, tt_b - tt_u * 4], [17.0, 17.5, 20], WHITE)  # flares into HT
_dt_end = ht_bot - hd * 28 - hn * 6                       # ends inside the head tube, just behind its axis
_dt_u = (_dt_end - v(10, 0, 8)).normalized()
_dt_len = (_dt_end - v(10, 0, 8)).length
DT_KNOTS = [(0.0, 27), (1 - 80 / _dt_len, 25), (1.0, 23)]
tube("down_tube", [v(10, 0, 8), _dt_end - _dt_u * 80], [27, 25], WHITE)
tube("down_tube_stub", [_dt_end - _dt_u * 100, _dt_end - _dt_u * 80, _dt_end], [24.5, 25, 23], WHITE)

def fuse(name, names, voxel=1.0, smooth=24):
    """Merge tube objects into one moulded surface: curves -> mesh, join, voxel remesh, then a
    volume-preserving smooth that rounds every tube-to-tube junction into a fillet (like the real frame)."""
    bpy.ops.object.select_all(action="DESELECT")
    obs = [bpy.data.objects[n] for n in names]
    for ob in obs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.convert(target="MESH")
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    rm = ob.modifiers.new("fuse", "REMESH")
    rm.mode, rm.voxel_size, rm.use_smooth_shade = "VOXEL", voxel * S, True
    lap = ob.modifiers.new("fillets", "LAPLACIANSMOOTH")
    lap.iterations, lap.lambda_factor, lap.use_volume_preserve = smooth, 1.0, True
    return ob

# front triangle junctions: head tube + top tube + down tube as one filleted surface
fuse("front_triangle", ["head_tube", "top_tube_stub", "down_tube_stub"])
def st_profile(s_):
    """Seat tube (lateral half-width, fore-aft half-depth) at distance s_ from the BB."""
    f = s_ / ST_LEN
    return 22 - 7 * f, 24 - 6 * f + 5 * max(0.0, f - 0.75) / 0.25

st_fwd = v(math.sin(sta), 0, math.cos(sta))
seat_tube = loft("seat_tube", [(ST_LEN * k / 16, *st_profile(ST_LEN * k / 16), 0) for k in range(17)],
                 WHITE, n=48, exp=(1, 1), subsurf=False)
seat_tube.rotation_euler = (0, sta + math.pi, 0)          # local X -> along the seat tube
cut_to_plane(seat_tube, ST_LEN, P_TOP, FRAME_N)            # top cut parallel to the frame line
cyl("bb_shell", v(0, 0, 0), 24, 86, WHITE)
for s, side in ((-1, "R"), (1, "L")):
    tube(f"chainstay_{side}",
         [v(-30, s * 36, 6), v(-210, s * 58, 42), rear + v(8, s * 64, 0)],
         [13, 11, 8], WHITE, smooth=True)
    ss_start = st_dir * (ST_LEN * 0.70) + v(0, s * 14, 0)
    tube(f"seatstay_{side}",
         [ss_start, (ss_start + rear) / 2 + v(0, s * 52, 0), rear + v(6, s * 64, 10)],
         [10, 8, 7], WHITE, smooth=True)
    # sculpted dropout: flat plate where chainstay and seatstay merge around the axle (IMG_6960-6962)
    d_cs = Vector((-210 - rear.x, 42 - BB_DROP)).normalized()
    d_ss = Vector((ss_start.x - rear.x, ss_start.z - BB_DROP)).normalized()
    pts = [(15 * math.cos(2 * math.pi * k / 24), 15 * math.sin(2 * math.pi * k / 24)) for k in range(24)]
    for d_, ln, hw in ((d_cs, 34, 9), (d_ss, 30, 7)):
        pn = Vector((-d_.y, d_.x))
        for sgn in (-1, 1):
            q = d_ * ln + pn * (sgn * hw)
            pts.append((q.x, q.y))
    def hull(points):
        P = sorted(set(points))
        def cross(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
        lower, upper = [], []
        for pt in P:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], pt) <= 0:
                lower.pop()
            lower.append(pt)
        for pt in reversed(P):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], pt) <= 0:
                upper.pop()
            upper.append(pt)
        return lower[:-1] + upper[:-1]
    extrude_profile(f"dropout_{side}", [hull(pts)], 60 if s > 0 else -70, 10, WHITE, origin=rear)
# BB shell + chainstays + seatstays + dropouts as one moulded rear end (filleted junctions, no flat stubs)
fuse("rear_triangle", ["bb_shell", "chainstay_R", "chainstay_L", "seatstay_R", "seatstay_L", "dropout_R", "dropout_L"])

# Frame decals: CANYON on down tube, ENDURACE SLX on top tube (both sides)
dt_a, dt_b = v(10, 0, 8), _dt_end
for side, tag in ((-1, "R"), (1, "L")):
    canyon_wordmark(f"decal_canyon_{tag}", side, tube_map(dt_a, dt_b, 27, 24, side, 0.6, knots=DT_KNOTS))
    glyph_decal(f"decal_endurace_slx_{tag}", "endurace_glyphs.json", 10.0,
                tube_map(tt_a, tt_b, 15, 18, side, 0.84, knots=TT_KNOTS), LOGO)

# The head tube is now a fused, smoothed surface: snap its logo onto the real surface.
sw = bpy.data.objects["canyon_headtube_logo"].modifiers.new("snap", "SHRINKWRAP")
sw.target = bpy.data.objects["front_triangle"]
sw.wrap_method, sw.wrap_mode, sw.offset = "NEAREST_SURFACEPOINT", "ABOVE_SURFACE", 0.5 * S

# Owner's VeloInk name sticker (Taiwan flag + "Kai") near the top of the seat tube
def seat_tube_map(side, below, lift, fwd=0.0):
    """Wrap onto the seat tube; x runs along the frame line, y along FRAME_N. Centre sits `below` mm
    under the seat-cluster top, shifted `fwd` mm along the frame line."""
    c0 = P_TOP - FRAME_N * below + tt_u * fwd
    def f(x, y):
        p = c0 + tt_u * (x if side < 0 else -x) + FRAME_N * y
        hw, hh = st_profile(p.dot(st_dir))
        lat = hw * math.sqrt(max(1 - (p.dot(st_fwd) / hh) ** 2, 0))
        return p + v(0, side * (lat + lift), 0)
    return f

def mask_mat(name, fname, color, rough=0.3, coat=0.0):
    """Solid colour cut out by a PNG's alpha (see make_textures.py)."""
    m = mat(name, color, rough=rough, coat=coat)
    path = os.path.join(OUT, fname)
    if not os.path.exists(path):
        print(f"[endurace] missing {fname}; run make_textures.py")
        return m
    tex = m.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(path, check_existing=True)
    tex.image.pack()
    m.node_tree.links.new(tex.outputs["Alpha"], m.node_tree.nodes.get("Principled BSDF").inputs["Alpha"])
    return m

def print_mat(name, fname, rough=0.55):
    """Printed graphic: colour and alpha from a PNG (see make_textures.py)."""
    m = mat(name, (0.8, 0.8, 0.8), rough=rough)
    path = os.path.join(OUT, fname)
    if not os.path.exists(path):
        print(f"[endurace] missing {fname}; run make_textures.py")
        return m
    nt = m.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(path, check_existing=True)
    tex.image.pack()
    b = nt.nodes.get("Principled BSDF")
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(tex.outputs["Alpha"], b.inputs["Alpha"])
    return m

TYRE_PRINT = print_mat("Schwalbe Sidewall Print", "tyre_print.png")
TYRE_PRINT_H = 8
TYRE_PRINT_W = TYRE_PRINT_H * 19.896                    # aspect from make_textures.py
ENVE_H = 34                                   # sticker height across the 42mm rim
ENVE_W = ENVE_H * 4.093                       # official logo aspect (make_textures.py)
ENVE_MAT = mask_mat("ENVE Sticker", "enve_logo.png", (0.88, 0.88, 0.86), rough=0.3, coat=1.0)
DECAL_WHITE = mat("Decal White", (0.9, 0.9, 0.9), rough=0.4)
TAG_WHITE = mat("Name Tag White", (0.95, 0.95, 0.95), rough=0.25)
FLAG_RED = mat("Flag Red", (0.85, 0.0, 0.0), rough=0.35)
FLAG_BLUE = mat("Flag Blue", (0.0, 0.0, 0.3), rough=0.35)
for side, tag in ((-1, "R"), (1, "L")):
    m_ = lambda lift: seat_tube_map(side, 1.5 + 5, lift, fwd=-3.5)  # ~1.5mm under the collar, ~6mm from the rear edge
    place(f"nametag_backing_{tag}", rect_bmesh(27, 10, 24, 8), m_(0.45), TAG_WHITE)
    place(f"nametag_flag_{tag}", rect_bmesh(9.5, 6.3, 10, 6), shifted(m_(0.7), -7, 0), FLAG_RED)
    place(f"nametag_canton_{tag}", rect_bmesh(4.75, 3.15, 6, 4), shifted(m_(0.9), -9.4, 1.6), FLAG_BLUE)
    place(f"nametag_sun_{tag}", disc_bmesh(0.9), shifted(m_(1.1), -9.4, 1.6), TAG_WHITE)
    decal(f"nametag_name_{tag}", "Kai", FONT_BOLD, 9, 5.5, shifted(m_(0.8), 6, 0), LOGO, cuts=3)

# ---------------------------------------------------------------- fork
t_axle = (ht_bot.z - BB_DROP) / math.sin(hta)
fork_offset = (front - (ht_bot + hd * t_axle)).dot(hn)
crown_top = ht_bot + hd * 4.8                                  # 0.8mm seam under the head tube
seam = loft("headset_seam", [(-1.2, 28.7, 30.2, 0), (0.4, 28.7, 30.2, 0)], DARK, n=48, exp=(1, 1), subsurf=False)
seam.location = crown_top * S
seam.rotation_euler = along(hd)
fork_crown = loft("fork_crown", [(0, 29.5, 31, 0), (6, 29.6, 30.4, 0), (14, 28.6, 28, 0), (22, 26.5, 24, 0),
                                  (30, 23, 18.5, 0), (36, 19, 13, 0)],
                  WHITE, n=48, exp=(1, 1), subsurf=False)       # same outline as the head tube bottom
fork_crown.location = crown_top * S
fork_crown.rotation_euler = along(hd)
for s, side in ((-1, "R"), (1, "L")):
    mid = ht_bot + hd * (t_axle * 0.5) + hn * (fork_offset * 0.3)
    tube(f"fork_blade_{side}",                                  # legs grow out of the crown -> arch between them
         [crown_top + hd * 16 + v(0, s * 14, 0), crown_top + hd * 40 + hn * 2 + v(0, s * 24, 0),
          mid + v(0, s * 46, 0), front + v(0, s * 52, 0)],
         [18, 16, 13, 9], WHITE, smooth=True)
# crown + legs as one moulded part: no flat-cut leg ends under the crown, filleted crown-to-leg blend
fuse("fork", ["fork_crown", "fork_blade_R", "fork_blade_L"])

# ---------------------------------------------------------------- wheels
ROTOR_STEEL = mat("Rotor Steel", (0.62, 0.62, 0.63), rough=0.38, metal=0.65)   # brushed: reads silver from any angle
ROTOR_Y = 53.1                                          # inboard face of the rotor (non-drive side)

def stadium_loop(cx, cz, ang, length, width, n=6):
    """Elongated slot centred at (cx, cz), long axis at angle ang."""
    ux, uz = math.cos(ang), math.sin(ang)
    px, pz = -uz, ux
    half, r = length / 2 - width / 2, width / 2
    pts = []
    for end, a0 in ((1, -math.pi / 2), (-1, math.pi / 2)):
        for k in range(n + 1):
            a = a0 + math.pi * k / n
            pts.append((cx + ux * (end * half + r * math.cos(a)) + px * r * math.sin(a),
                        cz + uz * (end * half + r * math.cos(a)) + pz * r * math.sin(a)))
    return pts

def paceline_rotor(name, c):
    """SRAM Paceline 160mm (owner photos IMG_6943/6944): steel track with two staggered rows of
    tangential slots, 6 curved arms to a centre ring, 6 silver Torx bolts on a black 6-bolt hub."""
    loops = [circle_loop(80, 160), circle_loop(17, 40)]
    for row, (rr, count, off) in enumerate(((68.5, 20, 0.0), (75.0, 20, 0.5))):
        for k in range(count):
            a = 2 * math.pi * (k + off) / count
            loops.append(stadium_loop(rr * math.cos(a), rr * math.sin(a), a + math.pi / 2, 9, 2.6))
    r0, r1, twist, hw = 29.0, 63.0, 0.55, 3.6           # arms: inner/outer radius, sweep, half-width
    for k in range(6):
        th0, th1 = 2 * math.pi * k / 6, 2 * math.pi * (k + 1) / 6
        win = []
        for j in range(9):                              # right edge of arm k, outward
            r_ = r0 + (r1 - r0) * j / 8
            a = th0 + twist * j / 8 + hw / r_
            win.append((r_ * math.cos(a), r_ * math.sin(a)))
        a_s, a_e = th0 + twist + hw / r1, th1 + twist - hw / r1
        win += [(r1 * math.cos(a_s + (a_e - a_s) * j / 10), r1 * math.sin(a_s + (a_e - a_s) * j / 10)) for j in range(1, 10)]
        for j in range(8, -1, -1):                      # left edge of arm k+1, inward
            r_ = r0 + (r1 - r0) * j / 8
            a = th1 + twist * j / 8 - hw / r_
            win.append((r_ * math.cos(a), r_ * math.sin(a)))
        a_s, a_e = th1 - hw / r0, th0 + hw / r0
        win += [(r0 * math.cos(a_s + (a_e - a_s) * j / 6), r0 * math.sin(a_s + (a_e - a_s) * j / 6)) for j in range(1, 6)]
        loops.append(win)
    extrude_profile(f"{name}_rotor", loops, ROTOR_Y, 1.8, ROTOR_STEEL, origin=c)
    y_out = ROTOR_Y + 1.8
    cyl(f"{name}_hub_flange", c + v(0, ROTOR_Y - 3, 0), 25, 6, DARK)
    cyl(f"{name}_hub_cap", c + v(0, y_out + 2, 0), 13, 4, DARK)
    for k in range(6):                                  # 44mm BCD Torx bolts
        a = 2 * math.pi * k / 6 + math.pi / 6
        bp = c + v(22 * math.cos(a), y_out + 1.1, 22 * math.sin(a))
        cyl(f"{name}_rotor_bolt_{k}", bp, 3.6, 2.2, METAL)
        cyl(f"{name}_rotor_bolt_torx_{k}", bp + v(0, 1.15, 0), 1.5, 0.3, DARK, verts=6)
    for txt, w, off in (("PACELINE 160mm", 22, 0), ("MIN. THICKNESS 1.55mm", 24, -3.6)):
        a = math.radians(150)
        rad_, tan_ = v(math.cos(a), 0, math.sin(a)), v(math.sin(a), 0, -math.cos(a))
        cen = c + rad_ * 46 + tan_ * off + v(0, y_out + 0.05, 0)
        decal(f"{name}_rotor_print_{off}", txt, FONT_COND, w, 2.4, lambda x, y, cen=cen, d=rad_, u=tan_: cen + d * x + u * y,
              LOGO, cuts=1)

def flat_mount_caliper(name, c, ang_deg, mount_to=None, port_fn=None):
    """SRAM flat-mount hydraulic caliper straddling the rotor at ang_deg (0 = forward, 90 = up)."""
    a = math.radians(ang_deg)
    rr, tt = v(math.cos(a), 0, math.sin(a)), v(-math.sin(a), 0, math.cos(a))
    p = c + rr * 70 + v(0, ROTOR_Y + 0.9, 0)
    rot = along(tt)
    box(f"{name}_body", p + v(0, 3, 0), (48, 30, 24), CARBON, rot=rot, bevel=5)
    box(f"{name}_bridge", p + rr * 9 + v(0, 3, 0), (40, 32, 7), CARBON, rot=rot, bevel=2.5)
    cyl(f"{name}_piston_cap", p + v(0, 18.6, 0), 12, 2.4, CARBON)
    cyl(f"{name}_piston_cap_inner", p + v(0, 19.9, 0), 9.5, 0.4, AXS_GREY)
    # hose fitting on the end nearest the frame; hose runs into an internal-routing port (owner photos)
    fit = p - tt * 21 + rr * 6 + v(0, 4, 0)
    tube(f"{name}_hose_fitting", [fit - tt * 2, fit - tt * 9], 4.2, DARK)
    if port_fn is not None:                             # port_fn(fit) -> (port position, port normal)
        port, port_n = port_fn(fit)
        mid = (fit + port) / 2 + port_n * 9
        tube(f"{name}_hose", [fit - tt * 8, mid, port + port_n * 1.5], 2.6, CARBON, smooth=True)
        g = cyl(f"{name}_hose_port", port + port_n * 0.6, 4.2, 1.6, DARK, axis="Z")
        g.rotation_euler = Vector((0, 0, 1)).rotation_difference(port_n).to_euler()
    for k in (-1, 1):                                   # mounting bolts
        cyl(f"{name}_mount_bolt_{k}", p + tt * (k * 15) - rr * 10 + v(0, 19, 0), 3.2, 2, METAL)
    sram_c = p + v(0, 18.3, 0) - tt * 0 + rr * 9
    decal(f"{name}_sram", "SRAM", FONT_HEAVY, 15, 3.4, lambda x, y: sram_c + v(0, 0.2, 0) + tt * x + rr * y,
          PRINT_GREY, cuts=1)
    if mount_to is not None:                            # flat-mount adaptor to the frame/fork
        d = mount_to - p
        d.y = 0
        box(f"{name}_adaptor", (p + mount_to) / 2 + v(0, 2, 0), (d.length + 10, 8, 18), CARBON,
            rot=along(d.normalized()), bevel=2)
    return p

HUB_BLACK = mat("DT Swiss Hub Black", (0.02, 0.02, 0.022), rough=0.35, metal=0.5)

def dt350_hub(name, c, y_left, y_right):
    """DT Swiss 350 (owner photos IMG_6954/6955): slim black shell between two spoke flanges,
    big '350' and 'DT SWISS' printed on the shell; rotor 6-bolt mount is on the left (disc) side."""
    tube(f"{name}_hub", [c + v(0, y_right, 0), c + v(0, y_left, 0)], 13, HUB_BLACK)
    for y_, tag in ((y_left, "L"), (y_right, "R")):
        cyl(f"{name}_hub_flange_{tag}", c + v(0, y_, 0), 24, 7, HUB_BLACK)
        cyl(f"{name}_hub_flange_lip_{tag}", c + v(0, y_ - math.copysign(4, y_), 0), 17, 3, HUB_BLACK)
    shell_mid = (y_left + y_right) / 2
    for k, phi0 in enumerate((math.radians(65), math.radians(245))):     # printed twice around the shell
        def shell_map(x, yy, phi0=phi0, yoff=0.0):
            phi = phi0 + yy / 13.0
            return c + v(13.3 * math.cos(phi), shell_mid + yoff + x, 13.3 * math.sin(phi))
        decal(f"{name}_hub_350_{k}", "350", FONT_HEAVY, 22, 9, lambda x, yy, f=shell_map: f(x, yy + 3), DECAL_WHITE,
              cuts=3)
        decal(f"{name}_hub_dtswiss_{k}", "DT SWISS", FONT_COND, 16, 2.8, lambda x, yy, f=shell_map: f(x, yy - 5),
              DECAL_WHITE, cuts=1)

def wheel(name, c, y_drive_flange=-34):
    torus(f"{name}_tire", c, R_BEAD + TIRE_W / 2, TIRE_W / 2, TIRE)
    torus(f"{name}_rim", c, R_BEAD - 21, 21, CARBON, lateral_scale=0.7)  # ED42: 42mm deep
    cu = bpy.data.curves.new(f"{name}_spokes", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 1.0 * S
    cu.bevel_resolution = 2
    for i in range(24):
        a = 2 * math.pi * i / 24
        side = 1 if i % 2 else -1
        hub_y = 36 if side > 0 else y_drive_flange       # spokes land on the DT 350 flanges
        hub = c + v(21 * math.cos(a + 0.3 * side), hub_y, 21 * math.sin(a + 0.3 * side))
        rim = c + v((R_BEAD - 42) * math.cos(a), 0, (R_BEAD - 42) * math.sin(a))
        sp = cu.splines.new("POLY")
        sp.points.add(1)
        sp.points[0].co = (*(hub * S), 1)
        sp.points[1].co = (*(rim * S), 1)
    add(bpy.data.objects.new(f"{name}_spokes", cu), DARK)
    dt350_hub(name, c, 36, y_drive_flange)
    cyl(f"{name}_axle", c, 9, 150, DARK)
    cyl(f"{name}_axle_cap", c + v(0, 75.5, 0), 13, 5, DARK)                       # non-drive end cap
    decal(f"{name}_axle_cap_print", "12 Nm  M12x1.0", FONT_COND, 18, 2.4,
          lambda x, y: c + v(-x, 78.1, y + 6.5), DECAL_WHITE, cuts=1)
    cyl(f"{name}_axle_nut", c + v(0, -75.5, 0), 11, 5, DARK, verts=6)              # drive-side nut
    paceline_rotor(name, c)
    rim_lat = lambda r_: 0.7 * math.sqrt(max(21 ** 2 - (r_ - (R_BEAD - 21)) ** 2, 0))
    tire_lat = lambda r_: math.sqrt(max(16 ** 2 - (r_ - (R_BEAD + 16)) ** 2, 0))
    for side, tag in ((-1, "R"), (1, "L")):
        for k in range(3):                                    # custom ENVE stickers, 120 deg apart
            place(f"{name}_enve_{tag}{k}", rect_bmesh(ENVE_W, ENVE_H, 80, 12),
                  ring_map(c, side, math.radians(90 + 120 * k), R_BEAD - 21, rim_lat), ENVE_MAT,
                  uv=(ENVE_W, ENVE_H))
        for k in range(2):
            place(f"{name}_schwalbe_{tag}{k}", rect_bmesh(TYRE_PRINT_W, TYRE_PRINT_H, 160, 4),
                  ring_map(c, side, math.radians(30 + 180 * k), R_BEAD + 9, tire_lat), TYRE_PRINT,
                  uv=(TYRE_PRINT_W, TYRE_PRINT_H))

wheel("rear_wheel", rear, y_drive_flange=-18)          # drive flange inboard of the cassette
wheel("front_wheel", front)

# Flat-mount brake calipers (non-drive side): front behind the fork leg, rear on top of the chainstay
_leg_dir = (ht_bot + hd * (t_axle * 0.5) + hn * (fork_offset * 0.3)) - front
_leg_dir.y = 0
_ld = _leg_dir.normalized()
_leg_back = -v(_ld.z, 0, -_ld.x)                                  # perpendicular to the leg, toward the rear
def _front_port(fit):
    """Port on the back of the left fork leg, ~70mm above the caliper fitting."""
    along_leg = (fit - front).dot(_ld)
    return front + _ld * (along_leg + 70) + _leg_back * 12 + v(0, 50, 0), _leg_back
flat_mount_caliper("front_caliper", front, 128, mount_to=front + _ld * 60 + v(0, 52, 0), port_fn=_front_port)
# rear hose leaves the underside of the left chainstay ~150mm ahead of the axle
_f = (rear.x + 150 + 210) / (rear.x + 8 + 210)
_cs = v(rear.x + 150, 58 + 6 * _f, 42 + (BB_DROP - 42) * _f)
_cs_n = v(0, -1, -0.35).normalized()                             # inner (wheel-side) face of the chainstay
flat_mount_caliper("rear_caliper", rear, 15, mount_to=rear + v(60, 58, 0),
                   port_fn=lambda fit: (_cs + _cs_n * 10, _cs_n))

# ---------------------------------------------------------------- pedals (Shimano PD-R550 SPD-SL)
RESIN = mat("Pedal Resin", (0.015, 0.015, 0.017), rough=0.45)

PEDAL_PLATE = mat("Pedal Plate", (0.55, 0.56, 0.58), rough=0.35, metal=1.0)
PEDAL_HANG = math.radians(10)                                  # nose-down hang

def pedal(name, crank_end, s):
    """Shimano PD-R550, traced from the owner's photo. Three zones front to back:
    open nose frame | solid platform under a chevron steel plate (2 slots, 4 screws) | raised rear binding.
    Local frame: x forward, y outward from the crank (pedal centre at y=42), z up."""
    rot = Matrix.Rotation(PEDAL_HANG, 3, "Y")
    eul = (0, PEDAL_HANG, 0)
    up_w = rot @ v(0, 0, 1)
    def L(x, y, z):
        return crank_end + rot @ v(x, s * y, z)
    tube(f"{name}_spindle", [L(0, -2, 0), L(0, 8, 0)], 6.5, METAL)
    tube(f"{name}_spindle_housing", [L(0, 6, 0), L(0, 14, 0)], 11, RESIN)

    # 1) nose: rounded-trapezoid resin frame around an open window
    def nose_pt(t):
        """Rounded rectangle (x 8..46, y +-27) tapering to +-20 at the nose; t in [0, 1)."""
        ang = 2 * math.pi * t
        c_, s_ = math.cos(ang), math.sin(ang)
        x = 27 + 19 * math.copysign(abs(c_) ** 0.35, c_)
        taper = 1 - 0.26 * (x - 8) / 38
        return x, 27 * taper * math.copysign(abs(s_) ** 0.35, s_)
    nose = [L(x, 42 + y, 0.5) for x, y in (nose_pt(k / 64) for k in range(64))]
    ribbon(f"{name}_nose_frame", nose, 12, 9, RESIN, lambda p, t: t.cross(up_w), closed=True)

    # 2) platform + chevron steel plate
    box(f"{name}_platform", L(-1, 42, 0), (24, 62, 13), RESIN, rot=eul, bevel=2.5)
    xf = lambda y: 9 - 4 * abs(y) / 30                       # plate front edge
    xr = lambda y: -10 - 4 * abs(y) / 30                     # plate rear edge
    pieces = []
    for sg in (-1, 1):
        y0, y1, y2, y3 = 0, 9 * sg, 21 * sg, 30 * sg
        pieces += [
            [(xr(y0), y0), (xf(y0), y0), (xf(y1), y1), (xr(y1), y1)],                     # centre
            [(xf(y1) - 5, y1), (xf(y1), y1), (xf(y2), y2), (xf(y2) - 5, y2)],             # front of slot
            [(xr(y1), y1), (xr(y1) + 5, y1), (xr(y2) + 5, y2), (xr(y2), y2)],             # rear of slot
            [(xr(y2), y2), (xf(y2), y2), (xf(y3), y3), (xr(y3), y3)],                     # outer end
        ]
    place(f"{name}_cleat_plate", shapes_bmesh(pieces, cuts=1), lambda x, y: L(x, 42 + y, 6.9), PEDAL_PLATE)
    for i, (x, y) in enumerate(((xf(27) - 2.5, -27), (xr(27) + 2.5, -27), (xf(27) - 2.5, 27), (xr(27) + 2.5, 27))):
        place(f"{name}_screw_{i}", disc_bmesh(1.6, 12), lambda px, py, x=x, y=y: L(x + px, 42 + y + py, 7.2), METAL)

    # 3) rear binding: raised block, top sloping down toward the back
    tilt = math.radians(-12)
    r_blk = Matrix.Rotation(PEDAL_HANG + tilt, 3, "Y")
    blk_c = L(-27, 42, 3)
    box(f"{name}_binding", blk_c, (30, 58, 16), RESIN, rot=(0, PEDAL_HANG + tilt, 0), bevel=3)
    top = blk_c + r_blk @ v(-2, 0, 8.15)
    d_, u_ = v(0, -1, 0), r_blk @ v(1, 0, 0)                 # reads toward the crank, tops forward
    decal(f"{name}_spdsl", "SPD-SL", FONT_HEAVY, 30, 6.5, lambda x, y: top + d_ * (x - 6 * s) + u_ * y,
          DECAL_WHITE, cuts=2)
    place(f"{name}_tension_hole", disc_bmesh(2.6, 16), lambda x, y: top + d_ * (x + 16 * s) + u_ * (y - 2) +
          r_blk @ v(0, 0, 0.1), DARK)

# ---------------------------------------------------------------- drivetrain (SRAM Rival eTap AXS 2x12)
# Traced from the owner's drive-side photo: chain on 48T x 36T, black one-piece chainrings with
# windows, silver 10-36 cassette, long-cage Rival AXS rear mech, Rival AXS front mech.
RING_BLACK = mat("Chainring Black", (0.022, 0.022, 0.025), rough=0.32, metal=0.6)
CASSETTE = mat("Cassette Steel", (0.72, 0.72, 0.74), rough=0.18, metal=1.0)
CHAIN_STEEL = mat("Chain Steel", (0.55, 0.55, 0.57), rough=0.32, metal=1.0)

R48, R35 = pitch_r(48), pitch_r(35)
RING_Y, RING35_Y = -47, -40.5                         # ring centre planes (2x chainline)

def cog_y(i):                                         # i: 0 = 10T (outboard) .. 11 = 36T (inboard)
    return -26 - (11 - i) * 3.4

# chainrings: big ring with a 4-window web, small ring visible through it
extrude_profile("chainring_48", [sprocket_loop(48), circle_loop(26, 32)] +
                [window_loop(48, R48 - 13, math.radians(90 * k + 14), math.radians(90 * k + 76), 14) for k in range(4)],
                RING_Y - 2, 4, RING_BLACK)
extrude_profile("chainring_35", [sprocket_loop(35), circle_loop(R35 - 11, 64)], RING35_Y - 1.5, 3, RING_BLACK)
lift_ring = lambda r_: -RING_Y + 2                     # print on the outer face of the big ring
decal("chainring_sram", "SRAM", FONT_HEAVY, 24, 5, ring_map(v(0, 0, 0), -1, math.radians(128), R48 - 9,
      lift_ring), DECAL_WHITE, cuts=2)
decal("chainring_spec", "48|35T   12 SPD", FONT_COND, 30, 3.4, ring_map(v(0, 0, 0), -1, math.radians(104), R48 - 9,
      lift_ring), PRINT_GREY, cuts=2)

# cranks (forged, tapered) + Quarq spindle cap
crank_ang = math.radians(8)
crank_len = CRANK_LENGTH
for s, ang in ((-1, crank_ang), (1, crank_ang + math.pi)):
    tag = "R" if s < 0 else "L"
    u = v(math.cos(ang), 0, math.sin(ang))
    arm = loft(f"crank_{tag}", [(-20, 8, 19, 0), (0, 9, 18, 0), (crank_len * 120 / 172.5, 8.5, 13, 0), (crank_len, 8, 11, 0), (crank_len + 11.5, 7, 9, 0)],
               RING_BLACK if s < 0 else CARBON)
    arm.location = v(0, s * 63, 0) * S
    arm.rotation_euler = along(u)
    pedal(f"pedal_{tag}", u * crank_len + v(0, s * 68, 0), s)
cyl("crank_spindle_cap", v(0, -72, 0), 14, 3, DARK)
place("quarq_ring", disc_bmesh(9, 32), lambda x, y: v(x, -73.6, y), PRINT_GREY)
decal("quarq_q", "Q", FONT_BOLD, 9, 10, lambda x, y: v(x, -73.9, y), DARK, cuts=2)

# cassette: 12 toothed cogs, windows in the big ones, freehub core
COGS = [10, 11, 12, 13, 15, 17, 19, 21, 24, 28, 32, 36]
cyl("cassette_core", rear + v(0, -44, 0), 17, 44, DARK)
for i, t in enumerate(COGS):
    loops = [sprocket_loop(t)]
    if t >= 21:
        loops += [circle_loop(19, 32)] + [window_loop(25, pitch_r(t) - 8, 2 * math.pi * k / 6 + 0.12,
                                                       2 * math.pi * (k + 1) / 6 - 0.12) for k in range(6)]
    else:
        loops += [circle_loop(pitch_r(t) - 7.5, 40)]
    extrude_profile(f"cog_{t}", loops, cog_y(i) - 0.8, 1.6, CASSETTE, origin=rear)

# rear derailleur geometry (relative to the axle, drive side view)
CHAIN_COG = 11                                        # 36T, as in the photo
cy = cog_y(CHAIN_COG)
U_P = rear + v(35, 0, -118)                            # upper jockey centre
L_P = rear + v(90, 0, -195)                            # lower jockey centre
R_JOCKEY = pitch_r(12)

# ---- chain: true tangent path, links every pitch
def chain_path(circles):
    """circles: (centre (x, z), r, dir +1 CCW / -1 CW, y) in travel order. Dense closed 3D polyline."""
    n, tang = len(circles), []
    for i in range(n):
        (a, ra, da, _), (b, rb, db, _) = circles[i], circles[(i + 1) % n]
        D = b - a
        th = math.atan2(D.y, D.x) - math.asin((rb * db - ra * da) / D.length)
        e = Vector((-math.sin(th), math.cos(th)))
        tang.append((a - e * (da * ra), b - e * (db * rb)))
    pts = []
    for i in range(n):
        c, r, d, y = circles[i]
        p_in, p_out = tang[i - 1][1], tang[i][0]
        a_in = math.atan2((p_in - c).y, (p_in - c).x)
        a_out = math.atan2((p_out - c).y, (p_out - c).x)
        sweep = (a_out - a_in) % (2 * math.pi) if d > 0 else -((a_in - a_out) % (2 * math.pi))
        steps = max(2, int(abs(sweep) * r))
        for k in range(steps + 1):
            ang = a_in + sweep * k / steps
            pts.append(v(c.x + r * math.cos(ang), y, c.y + r * math.sin(ang)))
        y_next = circles[(i + 1) % n][3]
        q0, q1 = tang[i]
        steps = max(2, int((q1 - q0).length))
        for k in range(1, steps):
            t = k / steps
            q = q0.lerp(q1, t)
            pts.append(v(q.x, y + (y_next - y) * t, q.y))
    return pts

def resample_closed(pts, pitch=PITCH):
    seg = [(pts[(i + 1) % len(pts)] - pts[i]).length for i in range(len(pts))]
    total = sum(seg)
    count = round(total / pitch)
    count += count % 2                                  # chains have an even number of links
    step, out, acc, i = total / count, [], 0.0, 0
    for k in range(count):
        target = k * step
        while acc + seg[i] < target:
            acc += seg[i]
            i += 1
        t = (target - acc) / seg[i] if seg[i] else 0
        out.append(pts[i].lerp(pts[(i + 1) % len(pts)], t))
    return out, step

def build_chain(name, pins, step, m):
    """Inner links (plates + rollers) alternate with outer links (plates + pin heads)."""
    half = step / 2
    def dogbone(rr, hw, n=8):
        a = math.asin(hw / rr)
        right = [(half + rr * math.cos(math.pi - a - (2 * math.pi - 2 * a) * j / n),
                  rr * math.sin(math.pi - a - (2 * math.pi - 2 * a) * j / n)) for j in range(n + 1)]
        left = [(-half + rr * math.cos(-a - (2 * math.pi - 2 * a) * j / n),
                 rr * math.sin(-a - (2 * math.pi - 2 * a) * j / n)) for j in range(n + 1)]
        return right + left
    def prism(outline, y0, y1):
        tris = tessellate_polygon([[Vector((x, z, 0)) for x, z in outline]])
        vs = [(x, y0, z) for x, z in outline] + [(x, y1, z) for x, z in outline]
        nn = len(outline)
        fs = [(a, b, c) for a, b, c in tris] + [(c + nn, b + nn, a + nn) for a, b, c in tris]
        fs += [(k, (k + 1) % nn, (k + 1) % nn + nn, k + nn) for k in range(nn)]
        return vs, fs
    def cylinder(x0, r, y0, y1, n=12):
        ring = [(x0 + r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n)) for k in range(n)]
        return prism(ring, y0, y1)
    inner = [prism(dogbone(4.7, 3.3), 1.15, 1.95), prism(dogbone(4.7, 3.3), -1.95, -1.15),
             cylinder(-half, 3.85, -1.15, 1.15), cylinder(half, 3.85, -1.15, 1.15)]
    outer = [prism(dogbone(4.5, 3.1), 1.95, 2.75), prism(dogbone(4.5, 3.1), -2.75, -1.95),
             cylinder(-half, 1.8, -3.0, 3.0, 8), cylinder(half, 1.8, -3.0, 3.0, 8)]
    bm = bmesh.new()
    for j in range(len(pins)):
        p0, p1 = pins[j], pins[(j + 1) % len(pins)]
        ux = (p1 - p0).normalized()
        uy = v(0, 1, 0) - ux * ux.y
        uy.normalize()
        uz = ux.cross(uy)
        c = (p0 + p1) / 2
        for vs, fs in (inner if j % 2 == 0 else outer):
            bv = [bm.verts.new((c + ux * x + uy * y + uz * z) * S) for x, y, z in vs]
            for f in fs:
                try:
                    bm.faces.new([bv[k] for k in f])
                except ValueError:
                    pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return add(bpy.data.objects.new(name, me), m)

xz = lambda p: Vector((p.x, p.z))
chain_pts = chain_path([
    (Vector((0, 0)), R48, +1, RING_Y),                 # big ring: bottom -> front -> top
    (xz(rear), pitch_r(COGS[CHAIN_COG]), +1, cy),      # cog: top -> rear -> bottom
    (xz(U_P), R_JOCKEY, -1, cy),                       # upper jockey (S-bend)
    (xz(L_P), R_JOCKEY, +1, cy),                       # lower jockey
])
pins, step = resample_closed(chain_pts)
build_chain("chain", pins, step, CHAIN_STEEL)
print(f"[endurace] chain: {len(pins)} links, pitch {step:.2f}mm")

# ---- rear derailleur (Rival eTap AXS)
for nm, pc in (("upper", U_P), ("lower", L_P)):
    extrude_profile(f"rd_jockey_{nm}", [sprocket_loop(12, tip=3.0), circle_loop(5, 16)], cy - 1.5, 3, DARK,
                    origin=v(pc.x, 0, pc.z))
    cyl(f"rd_jockey_bolt_{nm}", v(pc.x, cy - 6, pc.z), 4.5, 12, METAL)

def stadium(c1, c2, r1, r2, n=14):
    """Outline around two circles (cage plate), in (x, z) relative to the world origin."""
    d = (c2 - c1).normalized()
    a0 = math.atan2(d.y, d.x)
    pts = [(c2.x + r2 * math.cos(a0 - math.pi / 2 + math.pi * k / n),
            c2.y + r2 * math.sin(a0 - math.pi / 2 + math.pi * k / n)) for k in range(n + 1)]
    pts += [(c1.x + r1 * math.cos(a0 + math.pi / 2 + math.pi * k / n),
             c1.y + r1 * math.sin(a0 + math.pi / 2 + math.pi * k / n)) for k in range(n + 1)]
    return pts
# Rival eTap AXS rear mech, traced from owner photos IMG_6960-6962:
# black UDH hanger -> B-knuckle; upright battery with grey SRAM cover; silver-grey SRAM parallelogram
# link + black inner link, silver pivots; motor body with label/AXS; damper housing at the cage pivot;
# long black cage with a grey accent stripe; 12T X-Sync jockeys.
AXS_SILVER = mat("AXS Silver Grey", (0.36, 0.36, 0.38), rough=0.32, metal=0.6)
hanger = [(-8, 10), (12, 6), (8, -22), (-10, -38), (-22, -32), (-16, -4)]
extrude_profile("rd_udh_hanger", [hanger], -74, 4, DARK, origin=rear)
for k, (hx, hz) in enumerate(((-4, -10), (-13, -27))):
    cyl(f"rd_hanger_bolt_{k}", rear + v(hx, -74.6, hz), 3, 1.4, METAL)
knuckle = rear + v(-16, -70, -36)
box("rd_b_knuckle", knuckle, (24, 20, 28), CARBON, rot=(0, math.radians(15), 0), bevel=5)
batt_c = rear + v(-44, -68, -34)
batt_rot = (0, math.radians(-12), 0)
box("rd_battery", batt_c, (24, 26, 42), CARBON, rot=batt_rot, bevel=5)
box("rd_battery_cover", batt_c + v(0, -13.2, 0), (20, 0.8, 36), AXS_SILVER, rot=batt_rot, bevel=0.3)
b_up = Matrix.Rotation(math.radians(-12), 3, "Y") @ v(0, 0, 1)
decal("rd_battery_sram", "SRAM", FONT_HEAVY, 22, 5.5, lambda x, y: batt_c + v(0, -13.9, 0) + b_up * x + v(-1, 0, 0) * y,
      DECAL_WHITE, cuts=2)
motor_c = rear + v(22, -66, -96)
box("rd_motor_body", motor_c, (38, 28, 40), CARBON, rot=(0, math.radians(25), 0), bevel=8)
box("rd_motor_label", motor_c + v(-2, -14.3, 4), (22, 0.5, 16), AXS_GREY, rot=(0, math.radians(25), 0), bevel=0.3)
decal("rd_motor_axs", "AXS", FONT_HEAVY, 10, 3.6, lambda x, y: motor_c + v(x - 2, -14.8, y - 10), DECAL_WHITE, cuts=1)
# parallelogram: silver outer link (SRAM), black inner link, silver pivot bolts
pa, pb = rear + v(-14, -76, -46), rear + v(14, -76, -86)
pdv = pb - pa
pdv.y = 0
box("rd_parallelogram_outer", (pa + pb) / 2, (pdv.length + 10, 2.6, 18), AXS_SILVER, rot=along(pdv.normalized()), bevel=1)
box("rd_parallelogram_inner", (pa + pb) / 2 + v(-4, 16, 6), (pdv.length + 6, 3, 13), CARBON,
    rot=along(pdv.normalized()), bevel=1)
pdn = pdv.normalized()
pup = v(-pdn.z, 0, pdn.x)
decal("rd_parallelogram_sram", "SRAM", FONT_HEAVY, 18, 4.2, lambda x, y: (pa + pb) / 2 + v(0, -1.6, 0) + pdn * x + pup * y,
      PRINT_GREY, cuts=2)
for k, pp in enumerate((pa, pb)):
    cyl(f"rd_pivot_{k}", pp + v(0, -2, 0), 3.2, 2.4, METAL)
# damper housing at the cage pivot (upper jockey axis)
cyl("rd_cage_damper", v(U_P.x, cy - 12, U_P.z), 14, 8, CARBON)
cyl("rd_cage_damper_ring", v(U_P.x, cy - 16.2, U_P.z), 10, 0.6, AXS_GREY)
# cage: black outer plate with a grey accent stripe inlaid, black inner plate
cage = stadium(xz(U_P), xz(L_P), 17, 15)
extrude_profile("rd_cage_outer", [cage], cy - 7.5, 2.6, CARBON)
extrude_profile("rd_cage_accent", [stadium(xz(U_P), xz(L_P), 12, 10), stadium(xz(U_P), xz(L_P), 9, 7)],
                cy - 7.9, 0.4, AXS_GREY)
extrude_profile("rd_cage_inner", [stadium(xz(U_P), xz(L_P), 13, 12)], cy + 3.2, 1.8, CARBON)

# ---- front derailleur (Rival eTap AXS), traced from owner photos IMG_6947-6951:
# wedge battery (SRAM logo) on a motor body beside the seat tube, braze-on bolt, two curved link
# arms with H/L limit screws, polished silver winged outer cage (RIVAL) + black inner plate.
FD_SILVER = mat("FD Cage Polished", (0.9, 0.9, 0.92), rough=0.3, metal=0.85)
FD_ARM = mat("FD Arm Matte", (0.012, 0.012, 0.013), rough=0.8)
st_rot = (0, -(math.pi / 2 - sta), 0)                    # local Z along the seat tube
deg = math.radians
# cage: outer plate is a wing hugging the big ring, tail sweeping back and down
def r_top(a_deg):
    return R48 + 10 + 13 * ((141 - a_deg) / 46) ** 0.7
cage_outer = [((R48 + 6) * math.cos(deg(a_)), (R48 + 6) * math.sin(deg(a_))) for a_ in range(95, 142, 2)]
cage_outer += [(r_top(a_) * math.cos(deg(a_)), r_top(a_) * math.sin(deg(a_))) for a_ in range(141, 94, -2)]
extrude_profile("fd_cage_outer", [cage_outer], RING_Y - 10.6, 1.6, FD_SILVER)
cage_inner = [((R48 + 6) * math.cos(deg(a_)), (R48 + 6) * math.sin(deg(a_))) for a_ in range(98, 133, 3)]
cage_inner += [((R48 + 15) * math.cos(deg(a_)), (R48 + 15) * math.sin(deg(a_))) for a_ in range(132, 97, -3)]
extrude_profile("fd_cage_inner", [cage_inner], RING_Y + 4.0, 1.4, CARBON)
decal("fd_rival", "RIVAL", FONT_HEAVY, 22, 5, ring_map(v(0, 0, 0), -1, deg(120), R48 + 13,
      lambda r_: -(RING_Y - 10.6)), PRINT_GREY, cuts=2)
bridge = v((R48 + 26) * math.cos(deg(101)), RING_Y - 4, (R48 + 26) * math.sin(deg(101)))
box("fd_cage_bridge", bridge, (24, 18, 6), FD_SILVER, rot=along(v(-math.sin(deg(101)), 0, math.cos(deg(101)))), bevel=1.5)
for k, off in enumerate((-9, 9)):                        # tabs the link arms pivot on
    box(f"fd_cage_tab_{k}", bridge + v(off, -6, 6), (5, 3, 12), FD_SILVER, bevel=1)

# motor body against the seat tube, battery wedge on its outboard side
motor_c = v(-46, -36, 177)
box("fd_motor_body", motor_c, (26, 22, 34), CARBON, rot=st_rot, bevel=4)
batt_profile = [(-24, -14), (16, -14), (24, -2), (14, 18), (-18, 18), (-24, 6)]
batt_o = v(-58, 0, 185)
batt = extrude_profile("fd_battery", [batt_profile], -62, 20, CARBON, origin=batt_o)
bb = batt.modifiers.new("round", "BEVEL")
bb.width, bb.segments = 3 * S, 3
decal("fd_battery_sram", "SRAM", FONT_HEAVY, 20, 4.4, lambda x, y: batt_o + v(x - 2, -62.3, y + 2), DECAL_WHITE, cuts=2)
cyl("fd_braze_on_bolt", v(-64, -24, 167), 5.5, 7, DARK, axis="X", verts=6)

# two curved link arms from the motor down to the cage tabs, pivot bolts + H/L limit screws
for k, (top, bot) in enumerate(((v(-36, -47, 161), bridge + v(9, -8, 10)), (v(-54, -47, 161), bridge + v(-9, -8, 10)))):
    d_ = bot - top
    d_.y = 0
    box(f"fd_link_arm_{k}", (top + bot) / 2, (d_.length + 6, 4, 9), FD_ARM, rot=along(d_.normalized()), bevel=1.5)
    for pnt in (top, bot):
        cyl(f"fd_pivot_{k}_{int(pnt.z)}", pnt + v(0, -3, 0), 2.6, 3, METAL)
for k, dz in enumerate((8, -6)):                         # H (upper) and L (lower) limit screws
    cyl(f"fd_limit_screw_{k}", v(-30, -52, 150 + dz), 2.2, 2, METAL)

# ---------------------------------------------------------------- cockpit (PACE T-Bar)
# Headset stack (owner photos IMG_6972-6974): thin flared top cover on the head tube, one 10 mm aero
# spacer shaped like the stem footprint, then the tall CP0048 stem head (~56 mm) on the steerer.
up_s = -hd                                                        # up the steerer axis
HEAD_FOOT = (21.5, 23.5)                                          # stem/spacer footprint: lateral, fore-aft half sizes
COVER_H, SPACER_H, HEAD_H = 3.0, 10.0, 56.0
cover = loft("headset_cover", [(-1.0, 22.6, 25.4, 0), (1.2, 22.6, 25.4, 0), (3.0, HEAD_FOOT[0] + 0.6, HEAD_FOOT[1] + 0.6, 0)],
             CARBON, n=48, exp=(1, 1), subsurf=False)
cover.location = ht_top * S
cover.rotation_euler = along(up_s)
spacer_bot = ht_top + up_s * COVER_H
spacer = loft("headset_spacer_10mm", [(0, HEAD_FOOT[0] + 0.5, HEAD_FOOT[1] + 0.5, 0),
                                       (SPACER_H, HEAD_FOOT[0] + 0.5, HEAD_FOOT[1] + 0.5, 0)], CARBON, n=48, exp=(1, 1),
              subsurf=False)
spacer.location = spacer_bot * S
spacer.rotation_euler = along(up_s)
spacer_top = spacer_bot + up_s * SPACER_H
# the spacer's stepped split line on its front face
sp_front = lambda x, y: spacer_bot + up_s * (SPACER_H / 2 + y) + hn * (HEAD_FOOT[1] + 0.65) + v(0, x, 0)
place("headset_spacer_split", shapes_bmesh([
    [(-2.3, 0.2), (-1.7, 0.2), (-1.7, 5.0), (-2.3, 5.0)], [(-2.3, -0.2), (2.3, -0.2), (2.3, 0.4), (-2.3, 0.4)],
    [(1.7, -5.0), (2.3, -5.0), (2.3, -0.2), (1.7, -0.2)]], cuts=1), sp_front, DARK)
head_top = spacer_top + up_s * HEAD_H
# stem head: tall block on the steerer, softly rounded top edge
head_secs = [(-2.0, *HEAD_FOOT, 0), (HEAD_H - 8, HEAD_FOOT[0] + 0.3, HEAD_FOOT[1] + 0.3, 0),
             (HEAD_H - 4, HEAD_FOOT[0] - 0.6, HEAD_FOOT[1] - 0.6, 0), (HEAD_H - 1.5, HEAD_FOOT[0] - 4, HEAD_FOOT[1] - 4, 0),
             (HEAD_H - 0.2, HEAD_FOOT[0] - 9, HEAD_FOOT[1] - 9, 0)]
stem_head = loft("stem_head", head_secs, CARBON, n=56, exp=(0.85, 0.85), subsurf=False)
stem_head.location = spacer_top * S
stem_head.rotation_euler = along(up_s)
stem_up = math.radians((90 - HTA) - 6)               # -6 deg stem relative to steerer
NECK_HALF = 12.0
stem_base = head_top - up_s * NECK_HALF                           # neck centreline: top flush with the head top
bar_c = stem_base + v(math.cos(stem_up), 0, math.sin(stem_up)) * STEM_LENGTH
# neck: flat top flush with the head, big concave fillet underneath into the head front (side view),
# slim neck, then large fillets flaring into the bar tops (top view, IMG_6971)
stem_dir = (bar_c - stem_base).normalized()
L_ = (bar_c - stem_base).length
stem_secs = [(-10, 20, 12, 0), (8, 21, 24, -12), (16, 21, 19, -7), (24, 20.5, 15, -3), (32, 20.5, 12.5, -0.5)]
for f_, hw in ((L_ - 42, 21.5), (L_ - 34, 24.5), (L_ - 28, 29), (L_ - 24, 35),
               (L_ - 21, 43), (L_ - 18.5, 52), (L_ - 16.5, 60)):
    t_ = max(0.0, (f_ - 32) / (L_ - 16.5 - 32))
    stem_secs.append((f_, hw, 12 - 4 * t_, -4 * t_))              # top stays flush; thins to the bar's depth
stem_body = loft("stem", stem_secs, CARBON, n=48, exp=(0.55, 0.45), subsurf=False)   # flat top/bottom, round sides
stem_body.location = stem_base * S
stem_body.rotation_euler = along(stem_dir)
cap_top = head_top - up_s * 0.6                                   # top-cap bolt recessed in the stem head
cyl("stem_topcap_recess", cap_top, 8.5, 1.6, DARK, axis="Z")
cyl("stem_topcap_bolt", cap_top + v(0, 0, 0.6), 5.5, 1.2, METAL, axis="Z")
cyl("stem_topcap_torx", cap_top + v(0, 0, 1.25), 2.4, 0.2, DARK, axis="Z", verts=6)
# One-piece bar: bare-carbon flat aero tops (44x22 at the stem -> 32x16) sweep into taped halves whose
# section rounds off (-> 25mm round) through the bend, hood area and drop (owner photo IMG_6938).
TAPE_START = 150
tops_y = list(range(-TAPE_START, TAPE_START + 1, 5))
sweep("handlebar_tops", [bar_c + v(0, y, 0) for y in tops_y],
      [32 + 12 * max(0.0, 1 - abs(y) / 60) for y in tops_y], [16 + 6 * max(0.0, 1 - abs(y) / 60) for y in tops_y],
      CARBON, up0=v(0, 0, 1))
# one-piece T-bar: stem + tops fused, junctions smoothed into fillets (no seam/step at the bar)
stem_tbar = fuse("stem_tbar", ["stem_head", "stem", "handlebar_tops"], voxel=0.8, smooth=10)

# Stem head prints (IMG_6973): non-drive side, lower front -> CORE / BASE BAR / CP0048 / LENGTH 80 mm /
# CATEGORY 1; rear face: steerer-clamp bolt hole with "12 Nm".
def head_side_map(t_c, f_c, side=1, lift=0.35):
    """x = rearward along the side face (reads left-to-right from the left side), y = up the steerer."""
    def f(x, y):
        fa = f_c + x * side                                       # fore-aft offset (+ = rear)
        lat = HEAD_FOOT[0] * math.sqrt(max(1 - (fa / HEAD_FOOT[1]) ** 2, 0))
        return spacer_top + up_s * (t_c + y) - hn * fa + v(0, side * (lat + lift), 0)
    return f
PRINT_LIGHT = mat("Stem Print", (0.62, 0.62, 0.64), rough=0.5)
for txt, fnt, w, h, dy, dx in (("CORE", FONT_COND, 8.8, 4.0, 18.0, -1.2), ("BASE BAR", FONT_COND, 7.2, 1.5, 14.6, 0),
                               ("CP0048", FONT_COND, 8.8, 2.4, 11.4, -0.8), ("LENGTH %d mm" % STEM_LENGTH, FONT_COND, 13.6, 2.1, 8.1, -0.4),
                               ("CATEGORY 1", FONT_COND, 11.2, 2.1, 5.0, 0.4)):   # ~16mm block just above the spacer
    ob_ = decal(f"stem_print_{txt.split()[0].lower()}", txt, fnt, w, h, head_side_map(dy, -2 + dx), PRINT_LIGHT, cuts=1)
    sw = ob_.modifiers.new("snap", "SHRINKWRAP")
    sw.target, sw.wrap_method, sw.wrap_mode, sw.offset = stem_tbar, "NEAREST_SURFACEPOINT", "ABOVE_SURFACE", 0.3 * S
hole_c = spacer_top + up_s * 9 + hn * (-(HEAD_FOOT[1] + 0.2))      # rear face, low
hole = cyl("stem_clamp_bolt_hole", hole_c, 4.2, 1.0, DARK, axis="X")
cyl("stem_clamp_bolt_hex", hole_c - hn * 0.4, 2.0, 0.6, METAL, axis="X", verts=6)
decal("stem_print_12nm", "12 Nm", FONT_COND, 6, 1.9, lambda x, y: hole_c - hn * 0.3 + v(0, -x, 0) + up_s * (y + 7.5),
      PRINT_LIGHT, cuts=1)
for s, side in ((-1, "R"), (1, "L")):
    path = [bar_c + v(*q) for q in catmull([
        (0, s * TAPE_START, 0), (5, s * 176, -0.5), (22, s * 196, -3), (52, s * 205, -10),
        (80, s * 209, -50), (68, s * 212, -104), (24, s * 215, -127), (-45, s * 216, -130)], 90)]
    arc = [0.0]
    for i in range(1, len(path)):
        arc.append(arc[-1] + (path[i] - path[i - 1]).length)
    blend = [min(max(d - 16, 0.0) / 40.0, 1.0) for d in arc]   # stays flat under the finishing tape, then rounds
    chord = [33.6 + (26 - 33.6) * b_ for b_ in blend]        # bar + ~0.8mm of tape each side
    thick = [17.6 + (26 - 17.6) * b_ for b_ in blend]
    sweep(f"handlebar_{side}", path, chord, thick, TAPE, up0=v(0, 0, 1))
    ring_pts = [bar_c + v(0, s * y, 0) for y in range(TAPE_START - 2, TAPE_START + 14, 2)]
    sweep(f"bar_finishing_tape_{side}", ring_pts, [34.4] * len(ring_pts), [18.4] * len(ring_pts), FINISH_TAPE,
          up0=v(0, 0, 1))
    end_dir = (path[-1] - path[-2]).normalized()
    sweep(f"bar_end_plug_{side}", [path[-1] - end_dir * 1, path[-1] + end_dir * 3], [27, 27], [27, 27], DARK,
          up0=v(0, 0, 1))
    # SRAM Rival eTap AXS hood (owner photos IMG_6956-6958): long rubber body on the forward bend,
    # rising to a tall rounded horn, chevron grip texture
    hood = loft(f"hood_{side}", [(0, 14, 13, 0), (20, 15, 15, 2), (45, 15, 17, 6), (62, 14, 20, 12),
                                 (76, 13, 23, 20), (88, 11.5, 22, 28), (97, 9, 16, 34), (102, 5, 8, 37)], HOOD_RUBBER)
    hood.location = (bar_c + v(42, s * 205, -14)) * S
    hood.rotation_euler = (0, math.radians(-10), 0)
    # brake lever: glossy charcoal blade, wide under the horn, curving down and back to a flicked tip
    lev = [bar_c + v(*q) for q in catmull([(120, s * 206, 16), (126, s * 206, -30), (119, s * 207, -78),
                                           (105, s * 208, -112), (97, s * 209, -128), (101, s * 209, -138)], 40)]
    nl = len(lev)
    lev_w = [20 - 8 * k / (nl - 1) for k in range(nl)]                 # lateral width
    lev_d = [24 - 15 * (k / (nl - 1)) ** 0.8 for k in range(nl)]       # fore-aft depth: broad blade under the horn
    sweep(f"brake_lever_{side}", lev, lev_w, lev_d, LEVER_GLOSS, up0=v(1, 0, 0))
    # RIVAL down the outer face of the lever
    k0, k1 = int(nl * 0.32), int(nl * 0.62)
    l0, l1 = lev[k0], lev[k1]
    ld = (l1 - l0).normalized()
    lu = v(-ld.z, 0, ld.x) * (-s)
    lc = (l0 + l1) / 2 + v(0, s * (lev_w[(k0 + k1) // 2] / 2 + 0.5), 0)
    decal(f"brake_lever_rival_{side}", "RIVAL", FONT_HEAVY, 24, 5, lambda x, y, c=lc, d=ld, u=lu: c + d * x + u * y,
          PRINT_GREY, cuts=2)
    # shift paddle tucked behind the lever (toward the rider), ribbed, with the grey SRAM band
    def behind_lever(k):                                         # point just behind the lever's rear edge
        P, T = lev[k], (lev[min(k + 1, nl - 1)] - lev[max(k - 1, 0)]).normalized()
        F = v(-T.z, 0, T.x)
        F = F if F.x > 0 else -F
        return P - F * (lev_d[k] / 2 + 2.2) + v(0, -s * 2, 0)
    p0, p1 = behind_lever(int(nl * 0.38)), behind_lever(int(nl * 0.72))
    pd = (p1 - p0)
    pd.y = 0
    pc = (p0 + p1) / 2
    box(f"shift_paddle_{side}", pc, (pd.length, 18, 3), PADDLE_BLACK, rot=along(pd.normalized()), bevel=1.2)
    pn = v(-pd.normalized().z, 0, pd.normalized().x)               # paddle face normal (toward the rider: -x-ish)
    if pn.x > 0:
        pn = -pn
    box(f"shift_paddle_band_{side}", pc + pn * 1.6 - pd.normalized() * 14, (9, 18.2, 0.6), AXS_GREY,
        rot=along(pd.normalized()), bevel=0.2)
    for k in range(5):                                             # grip ribs
        box(f"shift_paddle_rib_{side}{k}", pc + pn * 1.7 + pd.normalized() * (k * 5 - 4), (1.2, 15, 0.8), PADDLE_BLACK,
            rot=along(pd.normalized()), bevel=0.3)

# ---------------------------------------------------------------- Canyon GEAR GROOVE mount + Bryton Rider S510
# Canyon GEAR GROOVE mount (IMG_6971): lens-shaped plate bolted on the stem top, overlapping the bar,
# with two slim arms running forward to the computer cradle.
def lens_loop(length, half_w, n=40):
    pts = []
    for k in range(n):
        t_ = 2 * math.pi * k / n
        c_, s_ = math.cos(t_), math.sin(t_)
        pts.append((length / 2 * c_, half_w * math.copysign(abs(s_) ** 0.75, s_)))
    return pts
def surface_z(x_mm, y_mm=0.0):
    """Top of the fused T-bar (evaluated mesh) at world x, y (mm), by casting a ray straight down."""
    dg = bpy.context.evaluated_depsgraph_get()
    hit, loc, *_ = scene.ray_cast(dg, Vector((x_mm * S, y_mm * S, 2.0)), Vector((0, 0, -1)))
    while hit and bpy.context.scene.objects.get("stem_tbar") is not None and not _[2].name.startswith("stem_tbar"):
        hit, loc, *_ = scene.ray_cast(dg, loc - Vector((0, 0, 1e-4)), Vector((0, 0, -1)))
    return loc.z / S
gg_mid = stem_base + stem_dir * (L_ - 26)
xa, xb = gg_mid.x - 22, gg_mid.x + 22                                   # plate rear / front contact points
za = max(surface_z(xa, -10), surface_z(xa, 10))
zb = max(surface_z(xb, -10), surface_z(xb, 10))
gg_fwd = v(xb - xa, 0, zb - za).normalized()
gg_n = v(-gg_fwd.z, 0, gg_fwd.x)                                         # plate normal (tilted with the stem)
gg_o = v(gg_mid.x, 0, (za + zb) / 2) + gg_n * 0.3
extrude_profile("gear_groove_plate", [lens_loop(58, 16)], 0, 4, CARBON, origin=gg_o,
                axes=(gg_fwd, v(0, 1, 0), gg_n))
for nm, off, r_, d_, m_ in (("gear_groove_plate_washer", 4.05, 6.2, 0.3, AXS_GREY),
                            ("gear_groove_bolt", 4.3, 4.2, 0.8, METAL), ("gear_groove_bolt_torx", 4.75, 1.8, 0.2, DARK)):
    ob_ = cyl(nm, gg_o - gg_fwd * 6 + gg_n * off, r_, d_, m_, axis="Z", verts=6 if "torx" in nm else 64)
    ob_.rotation_euler = Vector((0, 0, 1)).rotation_difference(gg_n).to_euler()
comp_c = bar_c + v(72, 0, 13)
for k, yy in enumerate((-9, 9)):                                       # arms: plate front -> computer cradle
    arm = [gg_o + gg_fwd * 24 + gg_n * 2 + v(0, yy, 0), comp_c + v(-12, yy, -9)]
    ribbon(f"gear_groove_arm_{k}", [arm[0] + (arm[-1] - arm[0]) * (j / 12) for j in range(13)], 5, 3, CARBON,
           lambda p, t: v(0, 0, 1))
box("gear_groove_cradle", comp_c + v(-6, 0, -9.5), (26, 30, 3), CARBON, bevel=1.2)
tilt = (0, math.radians(-8), 0)                                # screen tilted toward rider

def image_mat(name, fname, emit=0.0, alpha=False, rough=0.2):
    """Material driven by a PNG next to this script (see make_bryton_textures.py)."""
    m = mat(name, (0.02, 0.02, 0.02), rough=rough)
    path = os.path.join(OUT, fname)
    if not os.path.exists(path):
        print(f"[endurace] missing {fname}; run make_bryton_textures.py")
        return m
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(path, check_existing=True)
    tex.image.pack()
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    if emit:
        nt.links.new(tex.outputs["Color"], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = emit
    if alpha:
        nt.links.new(tex.outputs["Alpha"], b.inputs["Alpha"])
    return m

def image_quad(name, c, fwd, left, length, width, m):
    """Flat textured rectangle: image top points along fwd, image right is the rider's right."""
    corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    me = bpy.data.meshes.new(name)
    me.from_pydata([(c - left * (su * width / 2) + fwd * (sv * length / 2)) * S for su, sv in corners],
                   [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name="UVMap")
    for i, (su, sv) in enumerate(corners):
        uv.data[i].uv = ((su + 1) / 2, (sv + 1) / 2)
    return add(bpy.data.objects.new(name, me), m)

tilt_m = Matrix.Rotation(tilt[1], 3, "Y")
c_fwd, c_up = tilt_m @ v(1, 0, 0), tilt_m @ v(0, 0, 1)
box("bryton_s510_body", comp_c, (84, 56, 17), CARBON, rot=tilt, bevel=3)
c_bot = comp_c - c_up * 8.8 + c_fwd * 24                      # ahead of the mount puck
CORD = mat("Leash Cord", (0.012, 0.012, 0.013), rough=0.7)
loop_y = -58
bar_hw = (32 + 12 * max(0.0, 1 - abs(loop_y) / 60)) / 2 + 0.6       # bar half-chord + cord radius
bar_hh = (16 + 6 * max(0.0, 1 - abs(loop_y) / 60)) / 2 + 0.6
for k, dy in enumerate((0.0, -2.2)):                                  # two wraps
    wrap = []
    for j in range(48):
        t_ = 2 * math.pi * j / 48
        c_, s_ = math.cos(t_), math.sin(t_)
        wrap.append(bar_c + v(bar_hw * math.copysign(abs(c_) ** 0.6, c_),
                              loop_y + dy + 1.1 * s_ * (k * 2 - 1) * 0.3,
                              bar_hh * math.copysign(abs(s_) ** 0.6, s_)))
    tube(f"bryton_leash_wrap_{k}", wrap, 0.8, CORD, cyclic=True)
leash_anchor = comp_c - c_fwd * 41 + v(0, -27, 0) - c_up * 4          # lanyard tab, rear-right corner
toggle = bar_c + v(bar_hw + 10, loop_y + 2, -4)
tube("bryton_leash_cord", [bar_c + v(bar_hw, loop_y - 1, -2), toggle, leash_anchor + v(-4, -1, -2), leash_anchor],
     0.8, CORD, smooth=True)
tube("bryton_leash_cord_2", [bar_c + v(bar_hw, loop_y - 1, -2), toggle], 0.8, CORD, smooth=True)
tdir = (leash_anchor - toggle).normalized()
tube("bryton_leash_toggle", [toggle - tdir * 5, toggle + tdir * 5], [1.6, 2.4], CORD)
decal("bryton_s510_back_logo", "bryton", FONT_ROUNDED, 34, 7.5, lambda x, y: c_bot + v(0, 1, 0) * x + c_fwd * y,
      DECAL_GREY, cuts=2)
c_top = comp_c + c_up * 8.6
image_quad("bryton_s510_screen", c_top + c_fwd * 1, c_fwd, v(0, 1, 0), 58, 43,
           image_mat("Bryton Screen", "bryton_screen.png", emit=0.35, rough=0.12))
image_quad("bryton_s510_logo", c_top - c_fwd * 34, c_fwd, v(0, 1, 0), 7, 30,
           image_mat("Bryton Logo", "bryton_logo.png", alpha=True, rough=0.3))

# ---------------------------------------------------------------- bottle cages
def bottle_cage_x(name, base, axis, out, c_bands=False):
    """Down-tube cage (owner photos IMG_6935-6937): one-piece carbon "X" cage, mirror-symmetric.
    Backbone with 2 bolts (64mm) splitting into a Y whose arms reach the two top corners (no closed
    top ring); per side, a loop from that corner down around the bottle and back to the backbone
    bottom; J-hook foot at the bottom. c_bands=True (seat-tube cage, IMG_6939-6941) adds a top band and a
    middle band, both C-shaped and open at the front (no closed rings)."""
    lat = v(0, 1, 0)
    c0 = base + out * 40
    def pt(a, phi, r=38.5):
        return c0 + axis * a + (-out * math.cos(phi) + lat * math.sin(phi)) * r
    def nrm(p, tng):
        d = p - c0
        return d - axis * d.dot(axis)
    rad, W = math.radians, CARBON_WEAVE
    a_top = lambda phi: 124 + 6 * (1 - math.cos(phi)) / 2       # hoop rises a little toward the front
    bb = list(range(-2, 128, 3))
    ribbon(f"{name}_backbone", [pt(a, 0, 37.5) for a in bb],
           [9 + 6 * math.exp(-((a - 30) / 9) ** 2) + 6 * math.exp(-((a - 94) / 9) ** 2) for a in bb], 3, W, nrm)
    for sd, tag in ((-1, "R"), (1, "L")):
        y_arm = []
        for k in range(25):                                     # Y arm: top bolt -> hoop
            t = k / 24
            phi = rad(4 + 86 * t)                               # up to the top corner
            y_arm.append(pt(96 + (a_top(phi) - 96) * t ** 0.8, sd * phi))
        ribbon(f"{name}_y_arm_{tag}", y_arm, [11 - 3 * k / 24 for k in range(25)], 2.4, W, nrm)
        loop = catmull([(a_top(rad(90)), 90), (98, 128), (62, 150), (32, 138), (16, 72), (11, 16)], 48)
        ribbon(f"{name}_side_loop_{tag}", [pt(a, sd * rad(ph)) for a, ph in loop], 8, 2.3, W, nrm)
    if c_bands:
        gap = 28                                                # half-opening at the front (deg)
        ribbon(f"{name}_top_c", [pt(a_top(rad(d)), rad(d)) for d in range(-180 + gap, 181 - gap, 4)],
               12, 2.4, W, nrm)
        ribbon(f"{name}_mid_c", [pt(66, rad(d)) for d in range(-180 + gap + 6, 181 - gap - 6, 4)], 7, 2.2, W, nrm)
    ribbon(f"{name}_foot_hook", [pt(12, 0, 37.5), pt(3, 0, 36.5), pt(-4, 0, 31), pt(-6, 0, 23), pt(-3, 0, 15)],
           12, 2.6, W, lambda p, t: lat.cross(t))
    for a in (30, 94):
        cyl(f"{name}_bolt_{a}", pt(a, 0, 35.5), 4, 2, METAL, axis="Y").rotation_euler = \
            Vector((0, 0, 1)).rotation_difference(out).to_euler()

dt_u = (dt_b - dt_a).normalized()
dt_up = v(-dt_u.z, 0, dt_u.x)
dt_len = (dt_b - dt_a).length
s_dt = 0.40 * dt_len
dt_surf = dt_a + dt_u * s_dt + dt_up * (27 - 3 * s_dt / dt_len)
def tube_radius_at(s_):
    f_ = min(max(s_ / dt_len, 0.0), 1.0)
    for (f0, r0), (f1, r1) in zip(DT_KNOTS, DT_KNOTS[1:]):
        if f_ <= f1:
            return r0 + (r1 - r0) * (f_ - f0) / (f1 - f0)
    return DT_KNOTS[-1][1]

def curved_plate(name, s0, s1, half_w, thick, m, n_s=40, n_w=12):
    """Adapter plate conforming to the round down tube: rounded-end strip whose underside follows the
    tube surface; half_w (mm, lateral) stays well inside the tube width."""
    bm = bmesh.new()
    grid = {}
    for i in range(n_s + 1):
        s_ = s0 + (s1 - s0) * i / n_s
        end = min(i, n_s - i) / n_s * (s1 - s0)                  # distance to the nearest end (mm)
        hw = half_w * math.sqrt(max(0.0, 1 - max(0.0, 1 - end / half_w) ** 2)) if end < half_w else half_w
        hw = max(hw, 0.4)
        r_ = tube_radius_at(s_)
        for j in range(n_w + 1):
            lat = -hw + 2 * hw * j / n_w
            phi = lat / r_                                       # arc position around the tube
            for layer, rr in ((0, r_ + 0.2), (1, r_ + 0.2 + thick)):
                p = dt_a + dt_u * s_ + dt_up * (rr * math.cos(phi)) + v(0, rr * math.sin(phi), 0)
                grid[(i, j, layer)] = bm.verts.new(p * S)
    for i in range(n_s):
        for j in range(n_w):
            for layer in (0, 1):
                q = [grid[(i, j, layer)], grid[(i + 1, j, layer)], grid[(i + 1, j + 1, layer)], grid[(i, j + 1, layer)]]
                bm.faces.new(q if layer else q[::-1])
        for j, jn in ((0, 0), (n_w, n_w)):                       # side walls
            bm.faces.new([grid[(i, j, 0)], grid[(i + 1, j, 0)], grid[(i + 1, j, 1)], grid[(i, j, 1)]])
    for i in (0, n_s):                                           # end walls
        for j in range(n_w):
            bm.faces.new([grid[(i, j, 0)], grid[(i, j + 1, 0)], grid[(i, j + 1, 1)], grid[(i, j, 1)]])
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = add(bpy.data.objects.new(name, me), m)
    smooth_shade(ob)
    return ob

curved_plate("cage_adapter_plate", s_dt - 10, s_dt + 146, 15, 4, RESIN)   # 30mm wide on a ~52mm tube
bottle_cage_x("cage_downtube", dt_surf + dt_up * 4, dt_u, dt_up)
s_st = 160                                                     # lower bolt just above the front derailleur
bottle_cage_x("cage_seattube", st_dir * s_st + st_fwd * st_profile(s_st)[1], st_dir, st_fwd)  # same model as the DT cage

# ---------------------------------------------------------------- seatpost (Canyon SP0093 VCLS Aero)
POST_HW, POST_HH = 12.5, 19                                    # lateral / fore-aft half sizes
post_top = st_dir * (SADDLE_HEIGHT - 40)
post_len = SADDLE_HEIGHT - 40
seatpost = loft("seatpost", [(ST_LEN - 15, POST_HW, POST_HH, 0), (post_len, POST_HW, POST_HH, 0)],
                CARBON, n=48, exp=(0.75, 0.55), subsurf=False)
seatpost.rotation_euler = (0, sta + math.pi, 0)
collar = loft("seat_collar", [(ST_LEN - 1, POST_HW + 2.5, POST_HH + 2.5, 0), (ST_LEN + 7, POST_HW + 2, POST_HH + 2, 0)],
              RESIN, n=48, exp=(0.75, 0.55), subsurf=False)
collar.rotation_euler = (0, sta + math.pi, 0)
cut_to_plane(collar, ST_LEN - 1, P_TOP, FRAME_N, offset=-0.5, x_max=ST_LEN - 1)   # sits on the frame line ...
cut_to_plane(collar, ST_LEN + 7, P_TOP, FRAME_N, offset=8)                        # ... top parallel, 8mm up
# seat clamp cover: tab on the top tube just ahead of the collar, with its bolt
clamp_c = P_TOP + tt_u * (POST_HH + 17) + FRAME_N * 1.6
box("seat_clamp_cover", clamp_c, (30, 18, 3), RESIN, rot=along(tt_u), bevel=1.2)
place("seat_clamp_bolt", disc_bmesh(4, 20), lambda x, y: clamp_c + tt_u * (x - 4) + v(0, y, 0) + FRAME_N * 1.6, DARK)
post_tilt = (0, -(math.pi / 2 - sta), 0)
box("seatpost_head", post_top + st_dir * 4 - st_fwd * 4, (44, 30, 26), CARBON, rot=post_tilt, bevel=6)
for side, tag in ((-1, "R"), (1, "L")):
    cyl(f"seatpost_bolt_{tag}", post_top + st_dir * 6 - st_fwd * 4 + v(0, side * 15.5, 0), 6.5, 2, DARK)
    nm_c = post_top + st_dir * 15 - st_fwd * 4 + v(0, side * 15.3, 0)
    decal(f"seatpost_5nm_{tag}", "5 Nm", FONT_BOLD, 9, 2.6, lambda x, y, c=nm_c, sd=side: c + v(-sd * x, 0, y),
          DECAL_WHITE, cuts=1)
    cyl(f"seatpost_bolt_hex_{tag}", post_top + st_dir * 6 - st_fwd * 4 + v(0, side * 16.6, 0), 2.6, 0.6, RESIN,
        verts=6)
    # side print, reading up the post (letter tops toward the front on the left side)
    side_pt = st_dir * (ST_LEN + 28) + v(0, side * (POST_HW + 0.3), 0)
    up = st_fwd * side
    decal(f"seatpost_sp093_{tag}", "SP093", FONT_BOLD, 26, 6, lambda x, y, b=side_pt, u=up: b + st_dir * x + u * y,
          DECAL_GREY, cuts=2)
    decal(f"seatpost_vcls_{tag}", "VCLS AERO  SETBACK 10 MM / CATEGORY 1", FONT_COND, 52, 2.6,
          lambda x, y, b=side_pt, u=up: b + st_dir * (x + 46) + u * (y + 5.5), DECAL_GREY, cuts=1)

# ---------------------------------------------------------------- Canyon FLASH rear light (80 x 19 x 21 mm)
LENS = mat("Flash Lens", (0.5, 0.01, 0.01), rough=0.08, coat=1.0)
LED = mat("Flash LED", (1.0, 0.3, 0.1), rough=0.3)
for m_, col, strength in ((LENS, (1, 0.03, 0.02, 1), 3.0), (LED, (1, 0.35, 0.08, 1), 40.0)):
    bn = m_.node_tree.nodes.get("Principled BSDF")
    if "Emission Color" in bn.inputs:
        bn.inputs["Emission Color"].default_value = col
        bn.inputs["Emission Strength"].default_value = strength
light_c = st_dir * (ST_LEN + 52) - st_fwd * (POST_HH + 2 + 10.5)
box("flash_mount", st_dir * (ST_LEN + 52) - st_fwd * (POST_HH + 1), (3, 16, 60), RESIN, rot=post_tilt, bevel=1)
box("flash_body", light_c, (21, 19, 80), RESIN, rot=post_tilt, bevel=3)
box("flash_clip", light_c + st_dir * 42 + st_fwd * 6, (6, 10, 6), RESIN, rot=post_tilt, bevel=1.5)
box("flash_lens", light_c - st_fwd * 10.2, (1.6, 15, 74), LENS, rot=post_tilt, bevel=0.6)
box("flash_led_bar", light_c - st_fwd * 11.0, (0.8, 3, 64), LED, rot=post_tilt, bevel=0.3)

# ---------------------------------------------------------------- saddle (Fizik Aliante R5)
# Traced from 4 owner photos: 277 x 140mm pear outline, "wave" profile (tail ~22mm above the
# sit dip), black microfibre top over a grey side panel, centre perforation strip, embossed fizik
# near the tail, ALIANTE on the side near the nose, black alloy rails into two rear sockets.
SADDLE_TOP = mat("Saddle Microfibre", (0.018, 0.018, 0.019), rough=0.55)
SADDLE_SIDE = mat("Saddle Side Panel", (0.085, 0.085, 0.09), rough=0.65)
SADDLE_HOLE = mat("Saddle Perforation", (0.003, 0.003, 0.003), rough=0.9)
SADDLE_EMBOSS = mat("Saddle Emboss", (0.035, 0.035, 0.037), rough=0.35)
SADDLE_SECTIONS = [  # (x fwd from clamp, half-width, half-thickness, centre height)
    (-135, 32, 6, 30), (-127, 50, 9, 27), (-110, 62, 11, 21), (-85, 69, 12, 13), (-60, 70, 12, 6),
    (-35, 60, 12, 1), (-10, 45, 12, -1), (15, 32, 11, -1), (45, 25, 10, 0), (85, 21, 9, 1),
    (120, 19, 8, 0), (135, 15, 6, -1), (142, 7, 3, -2),
]

def saddle_at(x):
    """Interpolated (half-width, half-thickness, centre height) at x."""
    secs = SADDLE_SECTIONS
    x = min(max(x, secs[0][0]), secs[-1][0])
    for (x0, w0, h0, z0), (x1, w1, h1, z1) in zip(secs, secs[1:]):
        if x <= x1:
            f = (x - x0) / (x1 - x0)
            return w0 + (w1 - w0) * f, h0 + (h1 - h0) * f, z0 + (z1 - z0) * f

def saddle_top_z(x, y):
    hw, hh, zc = saddle_at(x)
    c = min(abs(y) / hw, 1.0) ** (1 / 0.7)
    return zc + hh * math.sqrt(max(1 - c * c, 0)) ** 0.9

def saddle_side_y(x, z):
    hw, hh, zc = saddle_at(x)
    sn = min(abs((z - zc) / hh), 1.0) ** (1 / 0.9)
    return hw * math.sqrt(max(1 - sn * sn, 0)) ** 0.7

saddle_c = post_top + v(15, 0, 40)
saddle = loft("saddle", SADDLE_SECTIONS, SADDLE_TOP, n=32)
saddle.location = saddle_c * S
saddle.data.materials.append(SADDLE_SIDE)
for poly in saddle.data.polygons:                     # grey side panel: lower half, tail to mid-nose
    cx, cz = poly.center.x / S, poly.center.z / S
    if cx < 90 and cz < saddle_at(cx)[2] + 1.5:
        poly.material_index = 1

# centre perforation strip (staggered holes)
holes = []
for i, x in enumerate(range(-42, 70, 4)):                 # ~33% .. 73% of the length from the tail
    for y in ((-4, 0, 4) if i % 2 == 0 else (-2, 2)):
        holes.append([(x + 0.85 * math.cos(2 * math.pi * k / 8), y + 0.85 * math.sin(2 * math.pi * k / 8))
                      for k in range(8)])
place("saddle_perforations", shapes_bmesh(holes, cuts=0),
      lambda x, y: saddle_c + v(x, y, saddle_top_z(x, y) + 0.9), SADDLE_HOLE)
# embossed fizik near the tail (reads toward the tail, seen from above)
decal("saddle_fizik", "fizik", FONT_BOLD, 34, 8, lambda x, y: saddle_c + v(-92 - x, -y, saddle_top_z(-92 - x, -y) + 0.9),
      SADDLE_EMBOSS, cuts=3)
# ALIANTE on the side, near the nose
for sd, tag in ((-1, "R"), (1, "L")):
    def side_map(x, y, sd=sd):
        xx = 92 + (x if sd < 0 else -x)
        zz = saddle_at(xx)[2] + 2 + y
        return saddle_c + v(xx, sd * (saddle_side_y(xx, zz) + 0.6), zz)
    decal(f"saddle_aliante_{tag}", "ALIANTE", FONT_COND, 30, 3.6, side_map, PRINT_GREY, cuts=2)
# black alloy rails: rear sockets -> under the shell -> clamp level -> nose
for sd, tag in ((-1, "R"), (1, "L")):
    tube(f"saddle_rail_{tag}", [saddle_c + v(-108, sd * 26, 8), saddle_c + v(-96, sd * 25, -10),
                                saddle_c + v(-60, sd * 25, -28), saddle_c + v(40, sd * 25, -28),
                                saddle_c + v(96, sd * 15, -10), saddle_c + v(118, sd * 9, 0)],
         3.5, CARBON, smooth=True)
    box(f"saddle_rail_socket_{tag}", saddle_c + v(-110, sd * 26, 10), (12, 12, 14), CARBON, bevel=3)

# ---------------------------------------------------------------- environment
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, ground_z * S))
add(bpy.context.active_object, mat("Floor", (0.6, 0.6, 0.6), rough=0.8)).parent = None

world = bpy.data.worlds.new("World")
scene.world = world
try:
    world.use_nodes = True
except Exception:
    pass
bg = world.node_tree.nodes.get("Background")
bg.inputs[0].default_value = (0.85, 0.87, 0.9, 1)
bg.inputs[1].default_value = 0.35
wn, wl = world.node_tree.nodes, world.node_tree.links
w_out = wn.get("World Output")
w_tc, w_sep, w_ramp = wn.new("ShaderNodeTexCoord"), wn.new("ShaderNodeSeparateXYZ"), wn.new("ShaderNodeValToRGB")
w_env, w_mix, w_lp = wn.new("ShaderNodeBackground"), wn.new("ShaderNodeMixShader"), wn.new("ShaderNodeLightPath")
wl.new(w_tc.outputs["Generated"], w_sep.inputs[0])
w_map = wn.new("ShaderNodeMath")
w_map.operation = "MULTIPLY_ADD"                                    # direction z: -1 floor .. +1 sky -> 0..1
w_map.inputs[1].default_value, w_map.inputs[2].default_value = 0.5, 0.5
wl.new(w_sep.outputs["Z"], w_map.inputs[0])
wl.new(w_map.outputs[0], w_ramp.inputs["Fac"])
cr = w_ramp.color_ramp
cr.elements[0].position, cr.elements[0].color = 0.35, (0.12, 0.12, 0.125, 1)   # dim floor, not black
cr.elements[1].position, cr.elements[1].color = 0.62, (1.0, 1.0, 1.0, 1)
mid = cr.elements.new(0.5)
mid.color = (0.6, 0.6, 0.62, 1)                                 # bright horizon -> silver reads silver
wl.new(w_ramp.outputs["Color"], w_env.inputs["Color"])
w_env.inputs["Strength"].default_value = 0.8
wl.new(w_lp.outputs["Is Camera Ray"], w_mix.inputs["Fac"])
wl.new(w_env.outputs[0], w_mix.inputs[1])                          # reflections / lighting
wl.new(bg.outputs[0], w_mix.inputs[2])                             # what the camera sees
wl.new(w_mix.outputs[0], w_out.inputs["Surface"])

sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
sun.data.energy = 2.5
sun.data.angle = math.radians(8)
sun.rotation_euler = (math.radians(40), math.radians(15), math.radians(-30))
scene.collection.objects.link(sun)
key = bpy.data.objects.new("Key", bpy.data.lights.new("Key", "AREA"))
key.data.energy = 400
key.data.size = 3
key.location = (0.5, -3.0, 2.5)
key.rotation_euler = (math.radians(50), 0, 0)
scene.collection.objects.link(key)
key_l = bpy.data.objects.new("Key_Left", key.data)          # mirrored key for the non-drive side
key_l.location = (0.5, 3.0, 2.5)
key_l.rotation_euler = (math.radians(-50), 0, 0)
scene.collection.objects.link(key_l)

def camera(name, loc, target, lens):
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    cam.data.lens = lens
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(cam)
    return cam

center = v((rear.x - R_TIRE + front.x + R_TIRE) / 2, 0, 330) * S
cam_side = camera("Cam_Side", center + Vector((0, -3.9, 0)), center, 70)
cam_34 = camera("Cam_ThreeQuarter", center + Vector((2.4, -2.8, 0.9)), center + Vector((0, 0, -0.05)), 60)
cam_left = camera("Cam_Left", center + Vector((0, 3.9, 0)), center, 70)
scene.camera = cam_side

r = scene.render
for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES"):
    try:
        r.engine = eng
        break
    except TypeError:
        continue
r.resolution_x, r.resolution_y = 1600, 1000
for look in ("AgX - Punchy", "Punchy"):
    try:
        scene.view_settings.look = look
        break
    except TypeError:
        continue
if r.engine == "CYCLES":
    scene.cycles.samples = 64

# open in Material Preview so decals/textures are visible (Solid mode hides image textures)
for scr in bpy.data.screens:
    for area in scr.areas:
        if area.type == "VIEW_3D":
            area.spaces[0].shading.type = "MATERIAL"
            area.spaces[0].clip_start = 0.001

blend_path = os.path.join(OUT, f"endurace_cf_slx_7_axs_{SIZE}.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"[endurace] size {SIZE}: fork offset {fork_offset:.1f}mm, engine {r.engine}, saved {blend_path}")

if RENDER:
    for cam, tag in ((cam_side, "side"), (cam_left, "left"), (cam_34, "34")):
        scene.camera = cam
        r.filepath = os.path.join(OUT, f"render_{SIZE}_{tag}.png")
        bpy.ops.render.render(write_still=True)
        print(f"[endurace] rendered {r.filepath}")
    scene.camera = cam_side
