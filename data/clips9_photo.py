# -*- coding: utf-8 -*-
"""Studio renders of the four clips, for showing a manufacturer what the part looks like.

    blender -b -P data/clips9_photo.py      ->  _clip_renders/frames/<code>_<view>.png
    python  data/clips9_photo_sheet.py      ->  _clip_renders/<code>.png

LOCAL ONLY.  _clip_renders/ is outside site/, so nothing here is published; these are pictures to
send someone, not a deliverable on the drawing register.  dxf/06 and S8 remain the drawings.

Not the flat light the board renders use.  That rig is calibrated so a surface renders at exactly
its own albedo, which is what makes the brick colours trustworthy and which gives steel no
highlight at all - it came out as grey paper.  Metal is read from the SHAPE OF THE REFLECTION, so
this builds its own studio: a bright top to the sky falling off towards the floor, and three broad
softboxes placed to draw a long highlight down the flat and across each fold.

The long clip is rendered at its FULL 1366, uncut, and again as a close-up of one end.
"""
import bpy, bmesh, json, math, os, sys
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_blender9 as B          # the clip geometry, so this is the part the model has

ROOT = os.path.abspath(os.path.join(HERE, '..'))
OUT = os.path.join(ROOT, '_clip_renders', 'frames')
os.makedirs(OUT, exist_ok=True)
S = B.S
PROF = B.PROF
CL = json.load(open(os.path.join(HERE, 'clips9.json'), encoding='utf-8'))['clips']
HOLE_R = 1.75*S

# view, camera direction, how much of the part to frame (None = all of it), pixels
SHOTS = (('hero',   Vector((-0.72, -0.80, 0.52)), None, (2600, 1500)),
         ('detail', Vector((-0.62, -0.66, 0.62)), 190.0, (1700, 1500)),
         ('end',    Vector((-0.30, -1.00, 0.16)), 120.0, (1700, 1500)))

# A 1366 part seen down a 45 deg azimuth crosses the frame corner to corner and ends up a tenth of
# the height of the picture.  Swung round to look nearly square-on it lies almost flat across the
# frame instead, and the whole length can be shown at a size worth looking at.
HERO_LONG = Vector((-0.14, -0.95, 0.28))
LONG_ASPECT = 6.0
# A pocket is a flat plate with three tabs standing off it.  Seen from the rail's own low
# angle it reads as a wall, and the plate - which is most of the part - disappears edge-on.
HERO_FLAT = Vector((-0.46, -0.58, 0.80))


def studio():
    """a sky with a top to it, and three softboxes: what makes steel look like steel"""
    w = bpy.data.worlds.new('studio'); bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes['Background']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    nt.links.new(tc.outputs['Generated'], sep.inputs['Vector'])
    nt.links.new(sep.outputs['Z'], ramp.inputs['Fac'])
    # Generated Z runs 0 at the nadir to 1 at the zenith.  BANDS, not a smooth gradient: a mirror
    # shows what is in front of it, and a sky that fades evenly gives the flat nothing to show but
    # an even field - which is what made the first attempt read as grey paper.  Bright and dark
    # bars put real edges into the reflection, and those edges are what the eye takes for polished
    # metal.  The floor is 0.26 and not near zero, or a vertical leg reflects only the dark half
    # of the sky and comes out as a hole in the part.
    FLOOR = 0.26
    e = ramp.color_ramp.elements
    e[0].position, e[0].color = 0.02, (FLOOR*0.5, FLOOR*0.5, FLOOR*0.55, 1)
    e[1].position, e[1].color = 0.30, (FLOOR, FLOOR, FLOOR*1.08, 1)
    for pos, v in ((0.42, 0.66), (0.50, FLOOR*1.3), (0.62, 0.82),
                   (0.72, FLOOR*1.5), (0.84, 0.58), (1.00, 0.34)):
        n = ramp.color_ramp.elements.new(pos)
        n.color = (v, v*1.01, v*1.05, 1)
    nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 2.4

    for name, loc, rot, size, energy in (
            ('key',  (-0.55, -0.42, 0.62), (0.72, 0.0, -0.92), 0.55, 150.0),
            ('fill', (0.66, -0.50, 0.34), (1.10, 0.0, 0.95), 0.70, 85.0),
            ('rim',  (0.20, 0.75, 0.50), (-0.95, 0.0, 0.25), 0.45, 110.0)):
        d = bpy.data.lights.new(name, 'AREA')
        d.shape, d.size, d.energy = 'RECTANGLE', size, energy
        d.size_y = size*0.28                      # a strip, so the highlight is a streak
        o = bpy.data.objects.new(name, d)
        o.location, o.rotation_euler = loc, rot
        bpy.context.scene.collection.objects.link(o)


def grade():
    """the tone curve, set AFTER setup_render, which deliberately turns it off

    build_blender9 renders the boards through 'Standard': albedo in, albedo out, no curve.  That
    is the whole basis of the colour calibration there, and it is exactly wrong here, because it
    also means no highlight roll-off - a polished face pointing at a lamp runs straight into the
    clip and prints as flat white.  AgX rolls the top end off instead, so the bright side of a
    fold stays the bright side of a fold.  A third of a stop down on top of that, because a part
    photographed on a light ground wants to sit under the paper rather than on it.
    """
    v = bpy.context.scene.view_settings
    for want in ('AgX', 'Filmic', 'Standard'):
        try:
            v.view_transform = want
            break
        except Exception:
            continue
    for look in ('AgX - Medium High Contrast', 'Medium High Contrast', 'None'):
        try:
            v.look = look
            break
        except Exception:
            continue
    v.exposure = -0.35
    v.gamma = 1.0


def steel():
    m = bpy.data.materials.new('steel'); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.62, 0.645, 0.68, 1.0)
    b.inputs['Metallic'].default_value = 1.0
    b.inputs['Roughness'].default_value = 0.20
    for k, v in (('Anisotropic', 0.45), ('Anisotropic Rotation', 0.0), ('IOR', 2.6)):
        if k in b.inputs:
            b.inputs[k].default_value = v
    return m


def clip_object(c):
    """the clip at its FULL length, holes cut through, sitting at the origin"""
    g = B.CLIPGEO[c['code']]
    holes = [tuple(q) for q in g['holes']]
    bm = bmesh.new()
    if c['kind'] == 'RAIL':
        L = c['length']
        B.clip_rail(bm, [(0.0, 0.0), (L, 0.0), (L, PROF['flat']), (0.0, PROF['flat'])], PROF)
    else:
        B.clip_pocket(bm, [tuple(q) for q in g['base']], g['lipped'], PROF,
                      g.get('tabs'), g.get('tab_w'))
    me = bpy.data.meshes.new('clip'); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(c['code'], me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(steel())
    for p in ob.data.polygons:
        p.use_smooth = False

    if holes:
        cyl = bmesh.new()
        for hx, hy in holes:
            bmesh.ops.create_cone(cyl, cap_ends=True, segments=40, radius1=HOLE_R,
                                  radius2=HOLE_R, depth=40*S,
                                  matrix=Matrix.Translation((hx*S, hy*S, 0.0)))
        cme = bpy.data.meshes.new('cut'); cyl.to_mesh(cme); cyl.free()
        cob = bpy.data.objects.new('cut', cme)
        bpy.context.scene.collection.objects.link(cob)
        m = ob.modifiers.new('holes', 'BOOLEAN')
        m.operation, m.object, m.solver = 'DIFFERENCE', cob, 'EXACT'
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.modifier_apply(modifier=m.name)
        bpy.data.objects.remove(cob, do_unlink=True)

    # A pocket is a flat plate lying face up.  Square to the lights it mirrors them across its
    # whole face and comes out as a sheet of white paper - the shading that says metal goes with
    # it.  Tipped a little, as anything gets tipped to be photographed, the face catches the
    # gradient instead of the lamp and the folds read.
    if c['kind'] == 'POCKET':
        ob.rotation_euler = (math.radians(7.0), math.radians(-17.0), 0.0)
        bpy.context.view_layer.update()

    # a touch off every hard arris.  A 0.25 sheet folded in a press has a radius on it, and a
    # perfectly sharp edge is the one thing that makes a render read as a drawing rather than a part
    bev = ob.modifiers.new('arris', 'BEVEL')
    bev.width, bev.segments, bev.limit_method = 0.09*S, 2, 'ANGLE'
    bev.angle_limit = math.radians(25)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=bev.name)
    return ob


def shot(ob, dirv, crop, res, path):
    for o in list(bpy.context.scene.objects):
        if o.type == 'CAMERA':
            bpy.data.objects.remove(o, do_unlink=True)
    cam = bpy.data.cameras.new('C'); cam.type = 'ORTHO'
    co = bpy.data.objects.new('C', cam)
    bpy.context.scene.collection.objects.link(co)
    bpy.context.scene.camera = co

    d = dirv.normalized()
    bb = [ob.matrix_world @ Vector(v) for v in ob.bound_box]
    cen = sum(bb, Vector())/8.0
    if crop:
        # frame the END of the part, which is where a fabricator looks: the return of the lip, the
        # cut face, the first hole
        x0 = min(p.x for p in bb)
        cen = Vector((x0+crop*S*0.5, cen.y, cen.z))
    up = Vector((0, 0, 1))
    r = d.cross(up).normalized()
    u2 = r.cross(d).normalized()
    if crop:
        w = h = crop*S
    else:
        w = max(abs((p-cen).dot(r)) for p in bb)*2
        h = max(abs((p-cen).dot(u2)) for p in bb)*2
    ar = res[0]/res[1]
    cam.ortho_scale = max(w/ar, h)*1.16*ar
    co.location = cen + d*3.0
    co.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()

    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent = True
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    for c in CL:
        B.wipe()
        studio()
        B.setup_render((1500, 1500), samples=384)
        grade()                       # after setup_render: it sets the boards' flat transform
        ob = clip_object(c)
        bb = [ob.matrix_world @ Vector(v) for v in ob.bound_box]
        span = max(p.x for p in bb)-min(p.x for p in bb)
        thick = max(p.y for p in bb)-min(p.y for p in bb)
        for tag, dirv, crop, res in SHOTS:
            if tag == 'hero' and span > LONG_ASPECT*thick:
                dirv, res = HERO_LONG, (3400, 1100)
            elif tag == 'hero' and c['kind'] == 'POCKET':
                dirv, res = HERO_FLAT, (2200, 1700)
            shot(ob, dirv, crop, res, os.path.join(OUT, '%s_%s.png' % (c['code'], tag)))
        print('%-10s %-7s  %g mm long, %d holes, %d faces'
              % (c['code'], c['kind'], c.get('length') or 0,
                 len(B.CLIPGEO[c['code']]['holes']), len(ob.data.polygons)))
    print('ALL DONE')
