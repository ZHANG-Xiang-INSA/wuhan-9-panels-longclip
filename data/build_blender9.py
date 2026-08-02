# -*- coding: utf-8 -*-
"""Build the nine boards in Blender: real slips, real clips, clay material, GLB per board and
EEVEE stills.  Run headless:

    blender -b -P build_blender9.py                 # all nine
    blender -b -P build_blender9.py -- --board=3    # just one
    blender -b -P build_blender9.py -- --probe      # light-rig calibration only

Geometry comes from site/data/boards.json, the same file the site loads, so the model and the
drawings cannot drift apart.  Each slip is its own polygon extruded 20 deep with a 0.5 chamfer on
the face arris; each clip is the M-section swept along its footprint, legs turned up and the return
lips hooked inward.

Three things the earlier version got wrong, all measured off its own output:

  colour   the area lights were unscaled, so a slip whose sampled albedo is #cdb48f came out at
           #fceabc, 1.75x over in linear.  The rig is now two SUN lamps plus a uniform world,
           balanced so that (Ek.cos0k + Ef.cos0f)/pi + S = 1.  A lambertian face-on surface then
           renders at exactly its albedo, and because a sun has no falloff the balance holds at
           any board size.  CAL_STOPS is the one measured correction, from --probe.
  evenness the same falloff made the bottom of a board 26 levels brighter than the top.  Suns do
           not fall off, so the field is flat.
  framing  camera.angle is the FOV across the LONGER sensor axis, so at 1800x1350 the vertical
           fit was short and every board overflowed the frame.  fit_camera() now iterates the real
           projection of the bounding box until both axes are inside.

The clay is driven off one UV set built here: each piece gets its own patch of noise, rotated to
its own long edge, so no two slips show the same grain.  Per-piece tone sits in a colour attribute
(mean 1.0, so it cannot shift the calibration), which glTF carries as COLOR_0 - the web viewer
reads the same two channels and gets the same variation.
"""
import bpy, bmesh, json, math, os, sys
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(bpy.data.filepath or __file__))
ROOT = os.path.abspath(os.path.join(HERE, '..')) if os.path.basename(HERE) == 'data' else \
    r'C:\Users\Stras\Documents\Claude\Projects\Brick slip PJ 001\wuhan-9-panels'
DATA = os.path.join(ROOT, 'site', 'data', 'boards.json')
MODELS = os.path.join(ROOT, 'site', 'models')
BLEND = os.path.join(ROOT, 'site', 'blend')
RENDERS = os.path.join(ROOT, 'site', 'renders')
os.makedirs(MODELS, exist_ok=True); os.makedirs(RENDERS, exist_ok=True)
os.makedirs(BLEND, exist_ok=True)

D = json.load(open(DATA, encoding='utf-8'))
BOARDS, PROF, CLIPGEO = D['boards'], D['profile'], D['clipgeo']
SLIP_T, PLATE, ARRIS = 20.0, 12.0, 0.5
S = 0.001                                   # millimetres to metres
CLIP_T = 0.25*S*4   # the clip's sheet, drawn thicker than 0.25 mm so it reads on screen

# ---------------------------------------------------------------------------- light rig
# direction FROM the board TOWARDS each lamp; cos to the face normal (0,0,1) is what balances
KEY_D, FILL_D = Vector((-0.42, -0.55, 0.72)), Vector((0.78, -0.50, 0.38))
WORLD_S = 0.32                              # uniform sky: irradiance pi * WORLD_S
FILL_RATIO = 0.30
CAL_STOPS = 0.0                             # measured by --probe; see the note in add_lights()

# tag, direction from the board, FOV, pad, resolution, crop width in mm (None = fit the board)
# A 1500 square 20 thick seen from high up reads as a floor tile, so hero stays near the normal
# and the third view stops fitting the board at all: it crops to half a metre at a grazing angle,
# which is the only one of the three where the arris, the joint shadow and the grain all show.
VIEWS = (('front',  (0.00, -0.05, 1.00), 29.0, 1.045, (1500, 1500), None),
         ('hero',   (0.36, -0.26, 0.90), 30.0, 1.050, (1800, 1200), None),
         ('detail', (0.66, -0.42, 0.62), 26.0, 1.000, (1800, 1200), 620.0))


def hexv(h):
    h = h.lstrip('#')
    lin = lambda c: c/12.92 if c <= 0.04045 else ((c+0.055)/1.055)**2.4
    return tuple(lin(int(h[i:i+2], 16)/255.0) for i in (0, 2, 4)) + (1.0,)


def rnd(i, k):
    """deterministic per-piece randomness, so two runs give the same board"""
    x = (i*2654435761 + k*40503 + 12345) & 0xffffffff
    x ^= x >> 13
    x = (x*1274126177) & 0xffffffff
    return ((x ^ (x >> 16)) & 0xffffffff)/4294967295.0


def wipe():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for c in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras,
              bpy.data.worlds, bpy.data.node_groups):
        for x in list(c):
            try: c.remove(x)
            except Exception: pass


# ---------------------------------------------------------------------------- shading
def sock(node, name, out=False):
    """the Mix node keeps one socket per data type under the same name; take the live one"""
    coll = node.outputs if out else node.inputs
    for s in coll:
        if s.name == name and s.enabled:
            return s
    return coll[name]


GAIN = {}
_gp = os.path.join(HERE, 'albedo_gain.json')
if os.path.exists(_gp):
    GAIN = json.load(open(_gp, encoding='utf-8'))


def backing_mesh(rect, w, h, plain, face):
    """the board, with the setting-out on the face the slips sit on and nothing on the back

    Two material slots on one mesh: the top face gets the setting-out, everything else - the back
    and the four 12 mm edges - stays plain board.  The first version put a planar UV on the whole
    prism and one material over it, so the marks came out on the back as well, mirrored, and
    smeared down the edges.

    glTF splits a mesh with two materials into two primitives, which reach the viewer as two
    meshes; app.js collects the backing as a list for that reason.
    """
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    prism(bm, rect, -PLATE*S, 0.0)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.faces.ensure_lookup_table()
    for f in bm.faces:
        top = f.normal.z > 0.999
        f.material_index = 1 if top else 0
        for lp in f.loops:
            # the board's own rectangle mapped to 0..1, so the setting-out lands on it at 1:1
            # whatever the board size.  Only the top face reads it.
            lp[uvl].uv = (lp.vert.co.x*1000.0/w+0.5, lp.vert.co.y*1000.0/h+0.5)
    me = bpy.data.meshes.new('backing'); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new('backing', me)
    ob.data.materials.append(plain)
    ob.data.materials.append(face)
    bpy.context.collection.objects.link(ob)
    return ob


def setout_mat(idx, base):
    """the backing board with its setting-out marked on it

    setout9_tex.py bakes the same lines and codes dxf/08 plots - every slip's outline, its clip's
    tray, the two fixing holes, and a code inside each - onto the board's own colour.  Switch the
    slips off in the viewer, or pull them off with the exploded view, and this is what is
    underneath, which is the whole point: the fitter reads the board.

    A texture rather than real line geometry.  The lines would be tens of thousands of extra edges
    per board in a file the website downloads, for something that is a surface mark on the real
    thing anyway.
    """
    m = bpy.data.materials.new('setout%d' % idx); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear(); L = nt.links.new
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = 0.94
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = 0.22
    p = os.path.join(ROOT, 'site', 'textures', 'setout_board_%d.png' % idx)
    if os.path.exists(p):
        img = bpy.data.images.load(p, check_existing=True)
        img.colorspace_settings.name = 'sRGB'
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = img
        tex.extension = 'EXTEND'
        uv = nt.nodes.new('ShaderNodeUVMap'); uv.uv_map = 'UVMap'
        L(uv.outputs['UV'], tex.inputs['Vector'])
        L(tex.outputs['Color'], bsdf.inputs['Base Color'])
    else:
        bsdf.inputs['Base Color'].default_value = base
    L(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return m


def clay(name, base, rough=0.87, relief=0.0009, grain=300.0, tint=True, gain=1.0):
    """Fired clay, four scales deep.

    mottle  26/m   ~40 mm cloud, the colour drifting across a face
    grain  300/m   ~3 mm, the sanded body - this is the one you actually read as texture
    grog   780/m   ~1.3 mm voronoi particles standing proud, thresholded so they stay sparse
    micro 1080/m   under the bump only, to stop the highlight going glassy

    Every noise is contrast-stretched before use.  Blender's normalised Fac is not uniform over
    0..1 - measured over a brick-length patch it sits between 0.39 and 0.62 at the 5th and 95th
    percentile - so feeding it straight into a +-14 % mix moved the colour by +-2.6 %, which is
    invisible.  STRETCH maps that measured band onto the full range; because the band is centred
    on 0.5 and clamped symmetrically, the mean stays at 0.5 and the calibration above still holds.
    """
    k = 0.105
    ST_MOT, ST_GRN, ST_MIC = 0.115, 0.098, 0.095
    base = tuple(min(1.0, c*gain) for c in base[:3])+(1.0,)
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear(); L = nt.links.new

    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    uv = nt.nodes.new('ShaderNodeUVMap'); uv.uv_map = 'UVMap'

    def noise(scale, detail, ro):
        n = nt.nodes.new('ShaderNodeTexNoise')
        n.inputs['Scale'].default_value = scale
        n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = ro
        L(uv.outputs['UV'], n.inputs['Vector'])
        return n.outputs['Fac']

    def math(op, a, b, clamp=False):
        n = nt.nodes.new('ShaderNodeMath'); n.operation = op; n.use_clamp = clamp
        for i, v in enumerate((a, b)):
            if hasattr(v, 'is_output'): L(v, n.inputs[i])
            else: n.inputs[i].default_value = v
        return n.outputs['Value']

    def band(v, lo, hi, a=1.0, b=0.0):
        n = nt.nodes.new('ShaderNodeMapRange'); n.clamp = True
        n.inputs['From Min'].default_value = lo
        n.inputs['From Max'].default_value = hi
        n.inputs['To Min'].default_value = a
        n.inputs['To Max'].default_value = b
        L(v, n.inputs['Value'])
        return n.outputs['Result']

    stretch = lambda v, a: band(v, 0.5-a, 0.5+a, 0.0, 1.0)

    n_mot = stretch(noise(26.0, 3.0, 0.55), ST_MOT)
    n_grn = stretch(noise(grain, 5.0, 0.62), ST_GRN)
    n_mic = stretch(noise(grain*3.6, 2.0, 0.50), ST_MIC)

    vor = nt.nodes.new('ShaderNodeTexVoronoi')
    vor.voronoi_dimensions = '2D'; vor.feature = 'F1'
    vor.inputs['Scale'].default_value = 780.0
    if 'Randomness' in vor.inputs:
        vor.inputs['Randomness'].default_value = 1.0
    L(uv.outputs['UV'], vor.inputs['Vector'])
    # F1 distance runs 0.12 .. 1.0 with the 5th percentile at 0.20, so this threshold leaves
    # roughly one speck in ten of area standing proud, with a hard edge
    grog = band(vor.outputs['Distance'], 0.14, 0.26, 1.0, 0.0)

    # colour factor: the two stretched scales only, weights summing to 1 so the mean stays at 0.5
    cfac = math('ADD', math('MULTIPLY', n_mot, 0.58), math('MULTIPLY', n_grn, 0.42))
    # height: everything, the particles carrying most of the bite.  Grog is deliberately kept out
    # of the colour - it is sparse and one-sided, so it would drag the mean off the sampled value
    hgt = math('ADD', math('ADD', math('MULTIPLY', n_mot, 0.30),
                           math('MULTIPLY', n_grn, 0.34)),
               math('ADD', math('MULTIPLY', grog, 0.26),
                    math('MULTIPLY', n_mic, 0.10)))

    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MIX'
    L(cfac, sock(mix, 'Factor'))
    sock(mix, 'A').default_value = tuple(c*(1.0-k) for c in base[:3])+(1.0,)
    sock(mix, 'B').default_value = tuple(min(1.0, c*(1.0+k)) for c in base[:3])+(1.0,)
    col = sock(mix, 'Result', out=True)

    if tint:                                            # per-piece tone, mean 1.0
        ca = nt.nodes.new('ShaderNodeVertexColor'); ca.layer_name = 'Col'
        tm = nt.nodes.new('ShaderNodeMix'); tm.data_type = 'RGBA'; tm.blend_type = 'MULTIPLY'
        sock(tm, 'Factor').default_value = 1.0
        L(col, sock(tm, 'A')); L(ca.outputs['Color'], sock(tm, 'B'))
        col = sock(tm, 'Result', out=True)

    rough_o = band(n_grn, 0.0, 1.0, min(1.0, rough+0.06), max(0.0, rough-0.06))  # hollows rougher

    bmp = nt.nodes.new('ShaderNodeBump')
    bmp.inputs['Strength'].default_value = 1.0
    bmp.inputs['Distance'].default_value = relief
    L(hgt, bmp.inputs['Height'])

    L(col, bsdf.inputs['Base Color'])
    L(rough_o, bsdf.inputs['Roughness'])
    L(bmp.outputs['Normal'], bsdf.inputs['Normal'])
    L(bsdf.outputs['BSDF'], out.inputs['Surface'])
    bsdf.inputs['Metallic'].default_value = 0.0
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = 0.32
    return m


def flat(name, base):
    """plain lambertian, used only by --probe"""
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = base
    b.inputs['Metallic'].default_value = 0.0
    b.inputs['Roughness'].default_value = 1.0
    if 'Specular IOR Level' in b.inputs:
        b.inputs['Specular IOR Level'].default_value = 0.0
    return m


def metal(name, base, rough=0.42):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = base
    b.inputs['Metallic'].default_value = 0.90
    b.inputs['Roughness'].default_value = rough
    return m


# ---------------------------------------------------------------------------- geometry
def prism(bm, poly, z0, z1):
    """Extrude one closed polygon between two heights.

    Returns the faces and verts it made, never their indices.  BMesh reuses freed element slots,
    so an index range taken before an operator does not still describe the same geometry after
    it - relying on one here silently re-beveled earlier pieces and flattened every UV.
    """
    vs = [bm.verts.new((p[0]*S, p[1]*S, z0)) for p in poly]
    if len(vs) < 3:
        for v in vs:
            bm.verts.remove(v)
        return None, None
    try:
        f = bm.faces.new(vs)
    except ValueError:
        for v in vs:
            if not v.link_faces:
                bm.verts.remove(v)
        return None, None
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    nv = [e for e in r['geom'] if isinstance(e, bmesh.types.BMVert)]
    nf = [e for e in r['geom'] if isinstance(e, bmesh.types.BMFace)]
    bmesh.ops.translate(bm, verts=nv, vec=(0, 0, z1-z0))
    return [f]+nf, vs+nv


def uv_frame(poly):
    """the longest edge sets the grain direction, the centroid the patch origin"""
    n = len(poly)
    bi, bl = 0, -1.0
    for i in range(n):
        ax, ay = poly[i]; bx, by = poly[(i+1) % n]
        d = (bx-ax)**2+(by-ay)**2
        if d > bl: bl, bi = d, i
    ax, ay = poly[bi]; bx, by = poly[(bi+1) % n]
    return (math.atan2(by-ay, bx-ax),
            sum(p[0] for p in poly)/n, sum(p[1] for p in poly)/n)


CELL = 240.0                    # mm; the bucket grid that locates a face in its piece


def inside(poly, x, y):
    c, n = False, len(poly)
    for i in range(n):
        ax, ay = poly[i]; bx, by = poly[(i+1) % n]
        if (ay > y) != (by > y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
            c = not c
    return c


def slip_mesh(polys, gids, name, mat):
    """One mesh per brick type: prisms, one chamfer over every top-edge ring, then UV and tone.

    The chamfer runs before the layers exist because bevel does not carry loop UVs onto the strips
    it makes - they came out at (0,0), which sampled the noise at the origin and left a rim of flat
    colour on every arris.  Locating each finished face in its own piece instead is immune to that,
    and to the element reshuffling that any bmesh operator is free to do.  A face is placed by its
    centroid pulled a little along -normal, so side walls and bevel strips - whose centroids sit
    exactly on the piece boundary - land unambiguously inside.
    """
    bm = bmesh.new()
    for poly in polys:
        prism(bm, poly, CLIP_T, CLIP_T+SLIP_T*S)
    zt = CLIP_T+SLIP_T*S            # the slip's face; it sits on the clip, so not SLIP_T*S alone
    eds = [e for e in bm.edges
           if abs(e.verts[0].co.z-zt) < 1e-7 and abs(e.verts[1].co.z-zt) < 1e-7]
    if eds:
        bmesh.ops.bevel(bm, geom=eds, offset=ARRIS*S, segments=2, profile=0.5,
                        affect='EDGES', clamp_overlap=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

    frame, grid = [], {}
    for k, (poly, gid) in enumerate(zip(polys, gids)):
        th, cx, cy = uv_frame(poly)
        t = 1.0+(rnd(gid, 3)-0.5)*0.18          # per-piece tone, mean 1.0 so calibration holds
        w = (rnd(gid, 4)-0.5)*0.05
        frame.append((poly, math.cos(-th), math.sin(-th), cx, cy,
                      rnd(gid, 1)*9.7, rnd(gid, 2)*7.3,
                      (t*(1.0+w), t, t*(1.0-w*0.7), 1.0)))
        xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
        for gx in range(int(math.floor(min(xs)/CELL)), int(math.floor(max(xs)/CELL))+1):
            for gy in range(int(math.floor(min(ys)/CELL)), int(math.floor(max(ys)/CELL))+1):
                grid.setdefault((gx, gy), []).append(k)

    uvl = bm.loops.layers.uv.new('UVMap')
    cl = bm.verts.layers.float_color.new('Col')
    lost = 0
    for f in bm.faces:
        c = f.calc_center_median()-f.normal*(0.4*S)
        x, y = c.x/S, c.y/S
        k = -1
        for j in grid.get((int(math.floor(x/CELL)), int(math.floor(y/CELL))), ()):
            if inside(frame[j][0], x, y):
                k = j; break
        if k < 0:                                # sliver too thin for the nudge: nearest centroid
            lost += 1
            k = min(range(len(frame)), key=lambda j: (frame[j][3]-x)**2+(frame[j][4]-y)**2)
        _, ca, sa, cx, cy, ox, oy, tone = frame[k]
        n = f.normal
        if abs(n.z) < 0.5:
            # the 20 deep reveal: an XY projection is constant up the edge, which smears the
            # grain into vertical streaks, so run u along the edge and v up the face
            t = Vector((-n.y, n.x, 0.0))
            t = t.normalized() if t.length > 1e-9 else Vector((1.0, 0.0, 0.0))
            for lp in f.loops:
                p = lp.vert.co
                lp[uvl].uv = ((p.x-cx*S)*t.x+(p.y-cy*S)*t.y+ox, p.z+oy)
                lp.vert[cl] = tone
        else:
            for lp in f.loops:
                px = lp.vert.co.x-cx*S; py = lp.vert.co.y-cy*S
                lp[uvl].uv = (px*ca-py*sa+ox, px*sa+py*ca+oy)
                lp.vert[cl] = tone
    dead = sum(1 for f in bm.faces if f.calc_area() < 1e-12)
    if dead or lost:
        print('   WARN %s: %d zero-area faces, %d faces placed by fallback, of %d'
              % (name, dead, lost, len(bm.faces)))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); ob.data.materials.append(mat)
    bpy.context.collection.objects.link(ob)
    return ob


def plain_mesh(polys, z0, z1, name, mat, uv_scale=1.0):
    # no colour layer here: the backing's material does not read one, and an unused one only
    # rides along into the GLB as a junk COLOR_0 the viewer then has to know to ignore
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    for p in polys:
        prism(bm, p, z0, z1)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.faces.ensure_lookup_table()
    for f in bm.faces:
        for lp in f.loops:
            lp[uvl].uv = (lp.vert.co.x*uv_scale, lp.vert.co.y*uv_scale)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); ob.data.materials.append(mat)
    bpy.context.collection.objects.link(ob)
    return ob


# ---------------------------------------------------------------------------- mortar
# A struck joint is not flat.  The mortar is pressed back from the brick arris and then tooled to a
# shallow concave groove down the middle of the joint, which is what gives brickwork its line of
# shadow.  Both figures scale with the joint: you cannot tool a 3 mm groove into a 3 mm joint.
SETBACK, GROOVE = 0.10, 0.38     # setback at the brick face, and depth at the joint centre, of J
BANDS = (0.0, 0.38, 0.70, 1.00)  # of the HALF joint, brick face to joint centre: three bands, so
                                 # the groove reads as a curve rather than a chamfer.  Measured in
                                 # real offset and not in ring index, or the deepest sample lands
                                 # wherever the last ring happens to be and the centre comes out
                                 # short - it read 0.360 J against the 0.38 J specified here.
LIP = 0.62                       # of J: past the centre the ring carries on flat at full depth,
                                 # so rings from facing slips overlap and no joint can end up with
                                 # a slot down the middle.  Still short of J, so a ring never
                                 # reaches the brick on the far side.
GAP = 0.05                       # mm the mortar stands off the brick face, and
BASE = 0.05                      # mm it stands off the backing.  No face of the mortar is then
                                 # coincident with a face of the brick or the board behind it.


def offset_out(poly, d):
    """mitred outward offset of a CCW polygon

    Mitred, not rounded, and that is the whole trick.  Offsetting every edge of a slip outward by
    half the joint and re-intersecting lands each corner on the medial axis of the joint: a 90
    degree corner mitres to d along both axes, which at a cross joint is exactly the joint's centre,
    and an acute corner mitres out to the point where the two neighbours would meet.  So the bands
    from neighbouring slips tile the joint with no gap to show the backing and no overlap to
    z-fight, whatever the bond.
    """
    n = len(poly)
    L = []
    for i in range(n):
        a, b = poly[i-1], poly[i]
        dx, dy = b[0]-a[0], b[1]-a[1]
        m = math.hypot(dx, dy) or 1.0
        L.append((a[0]+dy/m*d, a[1]-dx/m*d, dx/m, dy/m))
    out = []
    for i in range(n):
        x1, y1, u1, v1 = L[i]
        x2, y2, u2, v2 = L[(i+1) % n]
        den = u1*v2-v1*u2
        if abs(den) < 1e-9:
            out.append((x2, y2)); continue
        t = ((x2-x1)*v2-(y2-y1)*u2)/den
        out.append((x1+u1*t, y1+v1*t))
    return out


def ccw(poly):
    a = sum(poly[i-1][0]*poly[i][1]-poly[i][0]*poly[i-1][1] for i in range(len(poly)))
    return list(poly) if a > 0 else list(poly)[::-1]


def mortar_mesh(polys, rect, J, top, name, mat):
    """the joint fill, and nothing but the joint fill

    Mortar exists in the joints and nowhere else, so this is built as a ring of solid round each
    slip and there is no slab under the board.  The first version had one: a full-board box up to
    the groove floor, invisible because the slips are opaque and sitting inside every one of them.
    It looked right and was wrong, and it showed the moment the slips were switched off.

    Built in two parts, for two different reasons.

    THE BODY is the board slab from the backing up to the bottom of the groove, with every slip cut
    out of it by a boolean.  That is the only construction that is exact: pour it and it fills the
    joint, every corner of it, including the pockets a per-slip ring can never reach.  The first
    version tried rings alone and left a triangular hole at each apex where a herringbone V meets
    the border course - a point more than half a joint from all three bricks around it, so no
    slip's ring covered it, and the render showed the backing through it.

    THE DISH is the tooled groove, a ring of wedge per slip sitting on top of the body: from the
    groove plane up to the profile, deep at the joint centre and shallow at the brick.  Where a
    ring cannot reach, the body's own flat top is what shows, which is what a small pocket looks
    like in practice - there is no room to run an iron into it, so it stays full.

    The slips are dilated by GAP before they are cut out, and the body starts BASE above the
    backing.  Both are hairlines, and both are there so that no face of the mortar is coincident
    with a face of something else: a mortar wall in the same plane as the brick face it butts
    flickers against it under every renderer.
    """
    zg = top-GROOVE*J*S                      # the groove floor: the body's top, the dish's bottom
    body = plain_mesh([rect], BASE*S, zg, name, mat)
    cut = bmesh.new()
    for p in polys:
        prism(cut, offset_out(ccw(p), GAP), -PLATE*S, top+0.01)
    bmesh.ops.recalc_face_normals(cut, faces=cut.faces[:])
    me = bpy.data.meshes.new('_bricks'); cut.to_mesh(me); cut.free()
    knife = bpy.data.objects.new('_bricks', me)
    bpy.context.collection.objects.link(knife)
    md = body.modifiers.new('joints', 'BOOLEAN')
    md.operation, md.object, md.solver = 'DIFFERENCE', knife, 'EXACT'
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.modifier_apply(modifier='joints')
    bpy.data.objects.remove(knife, do_unlink=True)

    bm = bmesh.new()
    bm.from_mesh(body.data)
    uvl = bm.loops.layers.uv.active or bm.loops.layers.uv.new('UVMap')

    def face(*pts):
        try:
            bm.faces.new([bm.verts.new(p) for p in pts])
        except ValueError:
            pass

    # t runs 0 at the brick face to 1 at the joint centre, so GROOVE is delivered where it is
    # specified.  The extra entry is the flat lip that carries on past the centre at full depth.
    dep = [(SETBACK+(GROOVE-SETBACK)*math.sin(t*math.pi/2))*J*S for t in BANDS]+[GROOVE*J*S]
    rad = [GAP+(0.5*J-GAP)*t for t in BANDS]+[LIP*J]
    P = lambda r, k, z: (r[k][0]*S, r[k][1]*S, z)
    for p in polys:
        q = ccw(p)
        n = len(q)
        rings = [offset_out(q, d) for d in rad]
        I, O = rings[0], rings[-1]
        for i in range(n):
            j = (i+1) % n
            for k in range(len(rings)-1):
                A, B = rings[k], rings[k+1]
                za, zb = top-dep[k], top-dep[k+1]
                face(P(A, i, za), P(A, j, za), P(B, j, zb), P(B, i, zb))   # the tooled dish
            face(P(I, j, top-dep[0]), P(I, i, top-dep[0]),
                 P(I, i, zg), P(I, j, zg))                                 # wall against the brick
            face(P(I, i, zg), P(I, j, zg), P(O, j, zg), P(O, i, zg))       # seat on the body
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    # the dish may overhang the board where a slip sits on the outline, so it is cut back and the
    # cut capped: an open shell renders as a hollow, which is the whole fault being fixed here
    xs = [v[0] for v in rect]; ys = [v[1] for v in rect]
    for co, no in (((max(xs)*S, 0, 0), (1, 0, 0)), ((min(xs)*S, 0, 0), (-1, 0, 0)),
                   ((0, max(ys)*S, 0), (0, 1, 0)), ((0, min(ys)*S, 0), (0, -1, 0))):
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:]+bm.edges[:]+bm.faces[:],
                               plane_co=co, plane_no=no, clear_outer=True)
    bmesh.ops.holes_fill(bm, edges=bm.edges[:], sides=0)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.faces.ensure_lookup_table()
    for f in bm.faces:
        for lp in f.loops:
            lp[uvl].uv = (lp.vert.co.x*40.0, lp.vert.co.y*40.0)
    bm.to_mesh(body.data); bm.free()
    # the body was built into the scene collection so the boolean could be applied; the mortar has
    # to end up in MORTAR, on its own, or the Outliner's eye switches the wrong things
    for c in list(body.users_collection):
        c.objects.unlink(body)
    c = bpy.data.collections.get('MORTAR') or bpy.data.collections.new('MORTAR')
    if c.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(c)
    c.objects.link(body)
    return body


def fold_strip(bm, ra, rb, inw, sec, t):
    """One run of folded metal, as a SOLID strip of sheet thickness t.

    sec is the section the drawing dimensions - clips9_draw.section() and its pocket counterpart -
    given as (offset inward from the tray edge, height).  A drawing states sheet metal as one line
    and calls the thickness out separately, so the solid is swept t/2 either side of that line.

    The strip carried no thickness at all, and it should have.  Each face of it was run through
    extrude_face_region and then translated along +Z, which for a wall lies in the wall's own
    plane: the 0.6 went into HEIGHT and the leg came out as two coincident sheets of opposite
    winding joined by zero-area quads - 11376 of them across the nine boards.  So the fold was a
    razor standing in the plane of the tray's own edge, with no edge to it at the bend, and it
    read as detached from the plate it belongs to.  (It was not being culled away: coincident
    sheets of opposite winding always present a front face, and a depth comparison of front-side
    against double-side rendering differs by 0 pixels at 40 camera directions, before and after.)

    Each segment of the section is built as its OWN closed slab, and consecutive slabs are run
    half a thickness long at the bend so they overlap.  Offsetting the section as one polyline is
    what you would reach for, but the return lip turns back through 164 degrees, and a mitre at
    that angle throws the outer face 3.6 mm past the fold: the 15 mm leg measured 18.6.  Slabs
    that overlap need no mitre.  The leg is swept from height 0 so that it runs through the tray's
    own thickness, and it straddles the tray edge, so the bend is continuous metal rather than two
    solids meeting face to face.
    """
    for k, ((o0, h0), (o1, h1)) in enumerate(zip(sec, sec[1:])):
        eo, eh = o1-o0, h1-h0
        L = math.hypot(eo, eh)
        if L < 1e-12:
            continue
        eo, eh = eo/L, eh/L
        ext0 = t/2.0 if k else 0.0                       # run long into the bend, not past the end
        ext1 = t/2.0 if k < len(sec)-2 else 0.0
        a0, b0 = o0-eo*ext0, h0-eh*ext0
        a1, b1 = o1+eo*ext1, h1+eh*ext1
        mo, mh = eh*t/2.0, -eo*t/2.0                     # half the sheet, normal to the segment
        quad = ((a0+mo, b0+mh), (a1+mo, b1+mh), (a1-mo, b1-mh), (a0-mo, b0-mh))
        A = [bm.verts.new(((ra+inw*o).x, (ra+inw*o).y, h)) for o, h in quad]
        B = [bm.verts.new(((rb+inw*o).x, (rb+inw*o).y, h)) for o, h in quad]
        try:
            bm.faces.new(A[::-1])
            bm.faces.new(B)
        except ValueError:
            pass
        for i in range(4):
            j = (i+1) % 4
            try:
                bm.faces.new([A[i], A[j], B[j], B[i]])
            except ValueError:
                pass


def _runs(a, b, lipped, tab, tab_w):
    """the stretches of edge a->b that fold, mirroring clips9.lip_runs

    Kept as a few lines rather than an import because this file runs inside Blender's interpreter,
    which does not see the project's modules.  The rule is the one thing that must not drift, so it
    is stated here in full: nothing, the whole edge, or tab_w centred on it.
    """
    if not lipped:
        return []
    L = (b-a).length
    if not tab or L <= tab_w:
        return [(0.0, L)]
    return [((L-tab_w)/2.0, (L+tab_w)/2.0)]


def clip_pocket(bm, poly, lipped, prof, tabs=None, tab_w=None):
    """The dedicated pocket: a plate under the slip with lips turned up on the folded edges.

    Its footprint is the slip's own outline and can have any number of sides - board 8 has a
    three-sided and a five-sided one - so nothing here may assume a quad.  lipped[i] marks the
    edge running poly[i-1] -> poly[i], which is how clips9_build.offset_poly defines it and how
    it writes the flags.  poly is the clip's TRAY, which clips9_build.offset_poly has already
    stood LEGOUT = 1.5 outside the slip on every folded edge, so the leg rises on the tray line
    itself and the lip then hooks back in over the slip, which is the grip.
    """
    t = CLIP_T
    n = len(poly)
    pts = [Vector((q[0]*S, q[1]*S, 0.0)) for q in poly]
    vs = [bm.verts.new((p.x, p.y, 0.0)) for p in pts]      # on the backing, not sunk into it
    try:
        f = bm.faces.new(vs)
    except ValueError:
        for v in vs:
            if not v.link_faces:
                bm.verts.remove(v)
        return
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    bmesh.ops.translate(bm, verts=[e for e in r['geom'] if isinstance(e, bmesh.types.BMVert)],
                        vec=(0, 0, t))
    up, lip, tip = prof['leg']*S, prof['tip_in']*S, prof['tip_up']*S
    cen = Vector((sum(p.x for p in pts)/n, sum(p.y for p in pts)/n, 0.0))
    tabs = tabs or [False]*n
    for i in range(n):
        a, b = pts[i-1], pts[i]
        e = b-a
        if e.length < 1e-9:
            continue
        u = e.normalized()
        inw = Vector((-u.y, u.x, 0.0))
        if inw.dot(cen-a) < 0.0:
            inw = -inw
        # Offsets are measured inward from the tray edge, exactly as clip_rail measures from its own
        # footprint.  Backing the leg off by another sheet thickness here put the tray's 1.5 mm of
        # stand-off in twice and left the lip reaching only 0.26 mm over the slip, not the drawn
        # 1.26.  Heights are the rail's, so the two clip types present the same edge to the slip:
        # the leg is swept from 0 so it runs through the tray, and stands `up` proud of its face.
        sec = ((0.0, 0.0), (0.0, t+up), (lip, t+tip))
        for (r0, r1) in _runs(a, b, lipped[i], tabs[i], (tab_w or PROF['tab_w'])*S):
            fold_strip(bm, a+u*r0, a+u*r1, inw, sec, t)


def fit_motion(src, dst):
    """the rotation and translation that carries polygon src onto polygon dst

    The same recovery setout9._fit does, and for the same reason: boards.json carries each clip's
    placed TRAY but not its placed holes, so the motion is read back off the two polygons and then
    applied to the hole centres.  Both files must use this one, or the model's drill marks and the
    setting-out's drill marks drift apart.
    """
    n = min(len(src), len(dst))
    cs = (sum(q[0] for q in src)/len(src), sum(q[1] for q in src)/len(src))
    cd = (sum(q[0] for q in dst)/len(dst), sum(q[1] for q in dst)/len(dst))
    num = sum((src[i][0]-cs[0])*(dst[i][1]-cd[1])-(src[i][1]-cs[1])*(dst[i][0]-cd[0])
              for i in range(n))
    den = sum((src[i][0]-cs[0])*(dst[i][0]-cd[0])+(src[i][1]-cs[1])*(dst[i][1]-cd[1])
              for i in range(n))
    th = math.atan2(num, den)
    co, si = math.cos(th), math.sin(th)
    return lambda p: (cd[0]+(p[0]-cs[0])*co-(p[1]-cs[1])*si,
                      cd[1]+(p[0]-cs[0])*si+(p[1]-cs[1])*co)


def clip_rail(bm, quad, prof):
    """the M-section along a footprint: flat, two legs up, two lips hooked inward"""
    t = CLIP_T                     # drawn a little thicker than 0.25 so it reads on screen
    a, b, c, d = [Vector((q[0]*S, q[1]*S, 0)) for q in quad]
    u = (b-a); L = u.length
    if L < 1e-9:
        return
    u.normalize()
    v = (d-a); W = v.length
    if W < 1e-9:
        return
    v.normalize()
    lip, up, tip = prof['tip_in']*S, prof['leg']*S, prof['tip_up']*S
    # The backing's face is z = 0 and the clip is screwed onto it, so the flat occupies 0..t and
    # the slip rests on the flat.  Building it at -t..0 buried the clip inside the backing and put
    # its top face exactly on the backing's, which is what made the two flicker against each other.
    z0, z1 = 0.0, t
    p = [a, a+u*L, a+u*L+v*W, a+v*W]
    vs = [bm.verts.new((q.x, q.y, z0)) for q in p]
    try:
        f = bm.faces.new(vs)
    except ValueError:
        return
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    bmesh.ops.translate(bm, verts=[e for e in r['geom'] if isinstance(e, bmesh.types.BMVert)],
                        vec=(0, 0, z1-z0))
    # Same section and the same solid strip as the pocket, so the two clip types present an
    # identical edge to the slip and neither is a bare surface.
    sec = ((0.0, 0.0), (0.0, t+up), (lip, t+tip))
    for side, sgn in ((0.0, 1.0), (W, -1.0)):
        fold_strip(bm, a+v*side, a+u*L+v*side, v*sgn, sec, t)


# ---------------------------------------------------------------------------- scene
def world(strength=WORLD_S):
    w = bpy.data.worlds.new('W'); bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)   # neutral: the render IS the albedo
    bg.inputs['Strength'].default_value = strength


def add_lights():
    """Two suns balanced against the sky so a face-on lambertian surface renders at its albedo.

    A sun's Strength is irradiance normal to its own direction, so the contribution to the board
    face is E*cos(theta) and there is no distance term at all.  Solving

        (Ek*cos_k + Ef*cos_f)/pi + WORLD_S = 1,   Ef = FILL_RATIO * Ek

    fixes both energies once for every board, whatever its size.
    """
    ck = KEY_D.normalized().z
    cf = FILL_D.normalized().z
    ek = math.pi*(1.0-WORLD_S)/(ck+FILL_RATIO*cf)
    for nm, d, e, ang in (('key', KEY_D, ek, 12.0), ('fill', FILL_D, ek*FILL_RATIO, 34.0)):
        li = bpy.data.lights.new(nm, 'SUN')
        li.energy = e; li.angle = math.radians(ang)
        li.color = (1.0, 1.0, 1.0)
        ob = bpy.data.objects.new(nm, li); bpy.context.collection.objects.link(ob)
        ob.rotation_mode = 'QUATERNION'
        ob.rotation_quaternion = d.normalized().to_track_quat('Z', 'Y')
    return ek


def setup_render(res=(1800, 1200), samples=192):
    sc = bpy.context.scene
    ids = [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
    sc.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in ids else 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.render.image_settings.compression = 20
    sc.view_settings.view_transform = 'Standard'     # no filmic curve: albedo in, albedo out
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = CAL_STOPS
    sc.view_settings.gamma = 1.0
    ev = getattr(sc, 'eevee', None)
    if ev:
        for k, v in (('taa_render_samples', samples), ('use_raytracing', True),
                     ('use_shadows', True), ('use_gtao', True), ('use_bloom', False),
                     ('use_soft_shadows', True), ('shadow_ray_count', 2),
                     ('shadow_step_count', 6), ('use_shadow_jitter_viewport', True)):
            if hasattr(ev, k):
                try: setattr(ev, k, v)
                except Exception: pass
        rt = getattr(ev, 'ray_tracing_options', None)
        if rt is not None:
            for k, v in (('use_denoise', True), ('resolution_scale', '1')):
                if hasattr(rt, k):
                    try: setattr(rt, k, v)
                    except Exception: pass


def fit_camera(dirv, fov, pad, crop=None):
    """Frame everything on BOTH axes.

    camera.angle spans the longer sensor axis, so solving the fit from the board width alone left
    the short axis short.  Project the real bounding box instead and pull back until it is inside.
    """
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Matrix
    sc = bpy.context.scene
    cam = bpy.data.cameras.new('cam'); cam.lens_unit = 'FOV'; cam.angle = math.radians(fov)
    cam.sensor_fit = 'AUTO'
    co = bpy.data.objects.new('cam', cam); bpy.context.collection.objects.link(co)
    sc.camera = co
    d = Vector(dirv).normalized()
    # Roll has to be taken against the BOARD's up (+Y), not to_track_quat's global +Z: +Z here is
    # the face normal, so for any near-frontal view the reference is nearly parallel to the view
    # and the roll goes undefined - which is why the hero came out as a rotated diamond.
    z = d
    x = Vector((0.0, 1.0, 0.0)).cross(z)
    if x.length < 1e-6:
        x = Vector((1.0, 0.0, 0.0))
    x.normalize()
    y = z.cross(x)
    co.rotation_mode = 'XYZ'
    co.rotation_euler = Matrix((x, y, z)).transposed().to_4x4().to_euler()

    if crop:                                    # frame a fixed width instead of the whole board
        co.location = d*((crop*S/2.0)/math.tan(math.radians(fov/2.0))*pad)
        bpy.context.view_layer.update()
        return co

    pts = []
    for ob in bpy.context.collection.objects:
        if ob.type != 'MESH':
            continue
        for c in ob.bound_box:
            pts.append(ob.matrix_world @ Vector(c))
    if not pts:
        return co
    R = max(p.length for p in pts)*3.0
    for _ in range(8):
        co.location = d*R
        bpy.context.view_layer.update()
        m = 0.0
        for p in pts:
            v = world_to_camera_view(sc, co, p)
            m = max(m, abs(v.x-0.5)*2.0, abs(v.y-0.5)*2.0)
        if abs(m-1.0) < 0.002:
            break
        R *= max(0.25, m)
    co.location = d*R*pad
    bpy.context.view_layer.update()
    return co


# ---------------------------------------------------------------------------- probe
def probe():
    """Render two 2 m planes under the real rig and report what a known albedo comes back as.

    plane A is plain lambertian, plane B carries the clay shader; both are #cdb48f.  A tells you
    whether the light balance is right, B whether the noise is still symmetric about the base.
    """
    def srgb(c):
        return round(255*(12.92*c if c <= 0.0031308 else 1.055*c**(1/2.4)-0.055))
    # image.pixels on a byte image is the raw buffer over 255, NOT scene-linear: the view
    # transform has already encoded it.  Undo that here or the ratios come out per-channel wrong.
    def lin(c):
        return c/12.92 if c <= 0.04045 else ((c+0.055)/1.055)**2.4
    tgt = hexv('#cdb48f')
    wipe(); world(); setup_render((360, 180), 96)
    for i, (nm, mat) in enumerate((('A_flat', flat('A', tgt)),
                                   ('B_clay', clay('B', tgt, tint=False)))):
        me = bpy.data.meshes.new(nm)
        bm = bmesh.new()
        x0 = -2.0 if i == 0 else 0.02
        vs = [bm.verts.new(p) for p in ((x0, -1, 0), (x0+1.98, -1, 0),
                                        (x0+1.98, 1, 0), (x0, 1, 0))]
        bm.faces.new(vs); bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new(nm, me); ob.data.materials.append(mat)
        bpy.context.collection.objects.link(ob)
        if i == 1:
            me.uv_layers.new(name='UVMap')
            for lp in me.loops:
                me.uv_layers['UVMap'].data[lp.index].uv = me.vertices[lp.vertex_index].co.xy
    ek = add_lights()
    fit_camera((0.0, 0.0, 1.0), 30.0, 1.0)
    p = os.path.join(RENDERS, '_probe.png')
    bpy.context.scene.render.filepath = p
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(p)
    px = list(im.pixels)
    w, h = im.size
    acc = [[0.0]*3, [0.0]*3]; n = [0, 0]
    for y in range(h//4, h*3//4):
        for x in range(w):
            i = (y*w+x)*4
            if px[i+3] < 0.9:
                continue
            k = 0 if x < w*0.45 else (1 if x > w*0.55 else -1)
            if k < 0:
                continue
            for c in range(3):
                acc[k][c] += lin(px[i+c])
            n[k] += 1
    print('\n=== PROBE  target #cdb48f  linear %.4f %.4f %.4f' % tgt[:3])
    for k, nm in ((0, 'flat lambert'), (1, 'clay shader ')):
        if not n[k]:
            continue
        got = [acc[k][c]/n[k] for c in range(3)]
        r = [got[c]/tgt[c] for c in range(3)]
        print('  %s  linear %.4f %.4f %.4f   ratio %.3f %.3f %.3f   #%02x%02x%02x'
              % ((nm,)+tuple(got)+tuple(r)+tuple(srgb(g) for g in got)))
        mean = sum(r)/3.0
        print('     -> mean ratio %.4f   correction %+.4f stops' % (mean, -math.log2(mean)))
    print('=== key sun %.3f W/m2, fill %.3f, sky %.2f, exposure %+.4f\n'
          % (ek, ek*FILL_RATIO, WORLD_S, CAL_STOPS))


# ---------------------------------------------------------------------------- build
def build(b):
    wipe(); world()
    w, h = b['w'], b['h']
    cx, cy = w/2.0, h/2.0
    col = b['colour']
    # the slips are lifted by the measured self-occlusion of this bond so the FACE lands on the
    # sampled colour; the backing is not, it sits 20 down in the joint and is far more shaded
    g = float(GAIN.get(str(b['idx']), 1.0))
    m_brick = clay('brick%d' % b['idx'], hexv(col['brick']), gain=g)
    m_cut = clay('cut%d' % b['idx'], hexv(col['dark']), gain=g)
    m_back = setout_mat(b['idx'], hexv(col['mortar']))
    m_joint = clay('joint%d' % b['idx'], hexv(col['mortar']), rough=0.96, relief=0.0004,
                   grain=760.0, tint=False)
    # ONE FINISH PER CLIP TYPE, from data/clip_colours.json, and the same one on every board.
    # Every rail was the same steel, so a course carrying an R700, an R100 and an R50 read as one
    # continuous grey strip and nothing in the model said where one clip stopped.  Copper for the
    # 700, brass for the 100, blued steel for the 1000, plain steel for the 50 - and the pockets
    # keep their matt copper.  The colours are the ones the setting-out texture and the page use.
    CC = json.load(open(os.path.join(HERE, 'clip_colours.json'), encoding='utf-8'))
    m_clip = {c: metal('clip_'+c, tuple(v['metal'])+(1.0,), rough=v['rough'])
              for c, v in CC.items() if not c.startswith('_')}
    m_rail = m_clip['R50']

    cen = lambda p: [[q[0]-cx, q[1]-cy] for q in p]

    backing_mesh(cen([[0, 0], [w, 0], [w, h], [0, h]]), w, h,
                 clay('board%d' % b['idx'], hexv(col['mortar']), rough=0.94, relief=0.0006,
                      grain=520.0, tint=False), m_back)
    mortar_mesh([cen(p['p']) for p in b['pieces']], cen([[0, 0], [w, 0], [w, h], [0, h]]),
                b['joint'], CLIP_T+SLIP_T*S, 'MORTAR', m_joint)

    for ti, t in enumerate(b['types']):
        sel = [(i, p) for i, p in enumerate(b['pieces']) if p['t'] == ti]
        if not sel:
            continue
        slip_mesh([cen(p['p']) for _, p in sel], [i for i, _ in sel],
                  'T%02d_%s' % (ti+1, t['code']),
                  m_cut if t['kind'] == 'CUT' else m_brick)

    # ONE MESH PER CODE, gathered first and built once.  A clip of a given length can reach the
    # board two ways - as a member of a run, out of b['rails'], or as the one clip on a slip no
    # rail covers - and R50 now does both.  Built in two passes they came out as two meshes, the
    # second of which Blender renamed R50.001, so a viewer switching "R50" off switched half of
    # them off.  Which pass a clip came from is not a property of the clip.
    #
    # BY PIECE, not by code, for the second source.  The test used to be "is this code one of the
    # rail lengths", read off summary.rails - and the day R50 joined that list, because a 50 can
    # be a member of a run now, every slip that keeps its own R50 stopped being built.  703 clips
    # vanished out of the nine models and every check still passed, because nothing opened a GLB.
    covered = {i for lc in b.get('rails', []) for i in lc['covers']}
    # THE FOOTPRINT AND ITS TWO HOLES.  The clips in the model were solid: 60 triangles each,
    # which is the section swept round and nothing taken out of it, while the drawing and the
    # setting-out texture both showed the drill marks.  The holes go in here now, and they come
    # from the same place the drawing gets them - a rail carries its own two in board coordinates,
    # and a clip that sits on one slip has the type's holes carried onto that slip by the rigid
    # motion that put its tray there, which is exactly what setout9 does for dxf/08.
    foot = {}
    for lc in b.get('rails', []):
        foot.setdefault(lc['code'], []).append((lc['k'], [tuple(q) for q in lc['holes']]))
    for i, p in enumerate(b['pieces']):
        if i in covered:
            continue
        g = CLIPGEO.get(p['c'], {})
        hs = []
        if g.get('holes') and g.get('base') and len(g['base']) == len(p['k']):
            mv = fit_motion([tuple(q) for q in g['base']], [tuple(q) for q in p['k']])
            hs = [mv(tuple(q)) for q in g['holes']]
        foot.setdefault(p['c'], []).append((p['k'], hs))
    for code in sorted(foot):
        g = CLIPGEO.get(code, {})
        lip = g.get('lipped')
        acc = bmesh.new()
        for k, hs in foot[code]:
            q = cen(k)
            one = bmesh.new()
            if g.get('kind') == 'POCKET':
                tb = g.get('tabs') or [False]*len(q)
                clip_pocket(one, q, lip if lip and len(lip) == len(q) else [True]*len(q), PROF,
                            tabs=tb if len(tb) == len(q) else [False]*len(q),
                            tab_w=g.get('tab_w'))
            elif len(q) == 4:
                clip_rail(one, q, PROF)
            else:
                one.free()
                continue
            bmesh.ops.recalc_face_normals(one, faces=one.faces[:])
            if hs:
                # ONE CLIP AT A TIME.  Cutting a whole board's worth in a single boolean looks
                # cheaper and does not work: where the clips are dense or touching - board 9 is
                # laid on a 3 mm joint so neighbouring courses meet face to face, board 3 is a 45
                # deg herringbone - the EXACT solver is handed a mesh of 150 shells that touch and
                # returns it untouched.  Boards 2, 4, 6 and 7 came out with every hole and boards
                # 3, 9 and most of 8 with none at all, which is exactly what that failure looks
                # like.  Per clip the solver only ever sees one closed shell and two cylinders.
                tmp = bpy.data.meshes.new('one_'+code); one.to_mesh(tmp); one.free()
                tob = bpy.data.objects.new('one_'+code, tmp)
                bpy.context.collection.objects.link(tob)
                cyl = bmesh.new()
                for h in hs:
                    hx, hy = cen([h])[0]
                    bmesh.ops.create_cone(cyl, cap_ends=True, segments=20, radius1=1.75*S,
                                          radius2=1.75*S, depth=60*S,
                                          matrix=Matrix.Translation((hx*S, hy*S, 0.0)))
                cme = bpy.data.meshes.new('cut'); cyl.to_mesh(cme); cyl.free()
                cob = bpy.data.objects.new('cut', cme)
                bpy.context.collection.objects.link(cob)
                mod = tob.modifiers.new('holes', 'BOOLEAN')
                mod.operation, mod.object, mod.solver = 'DIFFERENCE', cob, 'EXACT'
                bpy.context.view_layer.objects.active = tob
                bpy.ops.object.modifier_apply(modifier=mod.name)
                acc.from_mesh(tob.data)
                bpy.data.objects.remove(cob, do_unlink=True)
                bpy.data.objects.remove(tob, do_unlink=True)
                bpy.data.meshes.remove(cme)
            else:
                tmp = bpy.data.meshes.new('one_'+code); one.to_mesh(tmp); one.free()
                acc.from_mesh(tmp)
                bpy.data.meshes.remove(tmp)
        me = bpy.data.meshes.new(code); acc.to_mesh(me); acc.free()
        ob = bpy.data.objects.new('CLIP_'+code, me)
        ob.data.materials.append(m_clip.get(code, m_rail))
        bpy.context.collection.objects.link(ob)

    add_lights()
    tris = sum(len(o.data.loop_triangles) if o.data.loop_triangles else
               sum(len(f.vertices)-2 for f in o.data.polygons)
               for o in bpy.context.scene.objects if o.type == 'MESH')
    return tris


# Everything below runs only when this file IS the script Blender was given.  clips9_photo.py
# imports it for the clip builders, the light rig and the materials, so that the renders it
# makes are the same metal, lit the same way, as the model the client already has - and an
# import must not rebuild all nine boards as a side effect.
if __name__ == '__main__':
    ARGS = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ONLY = None
    DO_GLB = '--no-glb' not in ARGS
    DO_PNG = '--no-png' not in ARGS
    DO_BLEND = '--no-blend' not in ARGS
    for a in ARGS:
        if a.startswith('--board='):
            ONLY = int(a.split('=')[1])

    if '--probe' in ARGS:
        probe()
        sys.exit(0)

    for b in BOARDS:
        if ONLY and b['idx'] != ONLY:
            continue
        setup_render()
        tris = build(b)
        print('BOARD %d  %s  %.0f x %.0f  %d pieces  %d types  %d tris'
              % (b['idx'], b['en'], b['w'], b['h'], len(b['pieces']), len(b['types']), tris))

        if DO_GLB:
            glb = os.path.join(MODELS, 'board_%d.glb' % b['idx'])
            for ob in bpy.context.scene.objects:
                ob.select_set(ob.type == 'MESH')
            kw = dict(filepath=glb, export_format='GLB', use_selection=True, export_apply=True,
                      export_yup=True, export_texcoords=True, export_normals=True,
                      export_cameras=False, export_lights=False)
            for k, v in (('export_vertex_color', 'ACTIVE'), ('export_all_vertex_colors', True),
                         ('export_attributes', True)):
                if k in bpy.ops.export_scene.gltf.get_rna_type().properties:
                    kw[k] = v
            bpy.ops.export_scene.gltf(**kw)
            print('   glb  %s  %.0f KB' % (os.path.basename(glb), os.path.getsize(glb)/1024))

        if DO_BLEND:
            # a .blend as well as the GLB: glTF carries no collections, so the mortar can only be
            # switched with the Outliner's eye if the file the client opens is a Blender file.  MORTAR
            # is its own collection and is left visible, so the board opens finished and one click
            # strips it back to bare brickwork.
            bl = os.path.join(BLEND, 'board_%d.blend' % b['idx'])
            # No .blend1 rolling backup.  site/ is uploaded as it stands, and every rebuild was leaving
            # nine backups of the PREVIOUS build in it - 3.8 MB of superseded models shipping alongside
            # the current ones under a name nobody would think to check.
            bpy.context.preferences.filepaths.save_version = 0
            bpy.ops.wm.save_as_mainfile(filepath=bl, copy=True)
            print('   blend %s  %.0f KB' % (os.path.basename(bl), os.path.getsize(bl)/1024))

        if DO_PNG:
            for tag, dirv, fov, pad, res, crop in VIEWS:
                setup_render(res)
                for ob in list(bpy.context.scene.objects):
                    if ob.type == 'CAMERA':
                        bpy.data.objects.remove(ob, do_unlink=True)
                fit_camera(dirv, fov, pad, crop)
                bpy.context.scene.render.filepath = \
                    os.path.join(RENDERS, 'b%d_%s.png' % (b['idx'], tag))
                bpy.ops.render.render(write_still=True)
                print('   png  b%d_%s.png  %dx%d' % (b['idx'], tag, res[0], res[1]))

    print('ALL DONE')
