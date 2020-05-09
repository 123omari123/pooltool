#! /usr/bin/env python
import psim.ani.utils as autils

from psim.ani import model_paths

import sys
import numpy as np

from panda3d.core import *
from direct.task import Task
from direct.actor.Actor import Actor
from direct.gui.OnscreenText import OnscreenText
from direct.showbase import DirectObject
from direct.showbase.ShowBase import ShowBase
from direct.interval.IntervalGlobal import Sequence


class Ball(object):
    def __init__(self, ball, rvw_history, euler_history, quat_history, node, use_euler=False):
        self.node = node
        self._ball = ball

        self.use_euler = use_euler

        self.xs = rvw_history[:,0,0]
        self.ys = rvw_history[:,0,1]
        self.zs = rvw_history[:,0,2]

        self.hs = euler_history[:,0]
        self.ps = euler_history[:,1]
        self.rs = euler_history[:,2]

        self.wxs = rvw_history[:,2,0]
        self.wys = rvw_history[:,2,1]
        self.wzs = rvw_history[:,2,2]

        self.quats = quat_history

        self.node.setScale(self.get_scale_factor())
        self.update(0)


    def get_scale_factor(self):
        """Find scale factor to match model size to ball's SI radius"""

        m, M = self.node.getTightBounds()
        current_R = (M - m)[0]/2

        return self._ball.R / current_R


    def update(self, frame):
        if self.use_euler:
            self.node.setHpr(self.hs[frame], self.ps[frame], self.rs[frame])
        else:
            self.node.setQuat(autils.get_quat_from_vector(self.quats[frame]))

        self.node.setPos(self.xs[frame], self.ys[frame], self.zs[frame] + self._ball.R)


class Handler(DirectObject.DirectObject):
    def __init__(self):
        self.accept('escape', sys.exit)
        self.accept('r', self.restart_shot)
        self.accept('space', self.pause_shot)
        self.accept('x', self.press_x)

        self.x_pressed = False

        # Game states
        self.pause = False
        self.birds_eye = False

    def restart_shot(self):
        self.frame = 0

    def pause_shot(self):
        self.pause = not self.pause

    def press_x(self):
        self.x_pressed = not self.x_pressed


class AnimateShot(ShowBase, Handler):
    def __init__(self, shot):
        ShowBase.__init__(self)
        Handler.__init__(self)
        self.taskMgr.add(self.master_task, "Master")

        self.frame = 0

        self.shot = shot
        self.shot.calculate_euler_angles()
        self.shot.calculate_quaternions()
        self.times = shot.get_time_history()
        self.num_frames = shot.n

        self.title = OnscreenText(text='psim',
                                  style=1, fg=(1, 1, 0, 1), shadow=(0, 0, 0, 0.5),
                                  pos=(0.87, -0.95), scale = .07)

        self.table = None
        self.init_table()

        self.balls = {}
        self.init_balls()

        self.scene = None
        self.init_scene()

        self.lights = {}
        self.init_lights()

        self.init_camera()


    def master_task(self, task):
        if not self.pause:
            for ball in self.balls.values():
                ball.update(self.frame)

            self.camera.setPos(
                self.balls['cue'].node.getX(),
                self.balls['cue'].node.getY()-1.4,
                self.balls['cue'].node.getZ()+1.2
            )
            self.camera.lookAt(self.balls['cue'].node)

            if self.frame >= self.num_frames:
                self.frame = 0
            else:
                self.frame += 1

        return Task.cont


    def restart_shot(self):
        self.frame = 0


    def init_scene(self):
        self.scene = self.loader.loadModel("models/environment")
        self.scene.reparentTo(self.render)
        self.scene.setScale(0.030, 0.030, 0.030)
        self.scene.setPos(0, 6.5, -0.7)


    def init_camera(self):
        self.disableMouse()
        self.camLens.setNear(0.2)
        self.camera.setPos(-1, -1, 1)
        self.camera.setHpr(-45, -30, 0)


    def init_table(self):
        w, l, h = self.shot.table.w, self.shot.table.l, self.shot.table.height

        self.table = self.render.attachNewNode(autils.make_square(
            x1=0, y1=0, z1=0, x2=w, y2=l, z2=0, name='playing_surface'
        ))

        self.table.setPos(0, 0, h)
        self.table.setTexture(self.loader.loadTexture(model_paths['blue_cloth']))


    def init_balls(self):
        for ball in self.shot.balls.values():
            self.balls[ball.id] = self.init_ball(ball)


    def init_ball(self, ball):
        rvw_history = self.shot.get_ball_rvw_history(ball.id)
        euler_history = self.shot.get_ball_euler_history(ball.id)
        quat_history = self.shot.get_ball_quat_history(ball.id)

        ball_node = self.loader.loadModel('models/smiley')
        ball_node.reparentTo(self.table)

        try:
            ball_node.setTexture(self.loader.loadTexture(model_paths[f"{str(ball.id).split('_')[0]}_ball"]), 1)
        except KeyError:
            # No ball texture is found for the given ball.id. Keeping smiley
            pass

        return Ball(ball, rvw_history, euler_history, quat_history, ball_node)


    def init_lights(self):
        w, l, h = self.shot.table.w, self.shot.table.l, self.shot.table.lights_height

        self.lights['ambient'] = {}
        self.lights['overhead'] = {}

        overhead_intensity = 0.3

        def add_overhead(x, y, z, name='plight'):
            plight = PointLight(name)
            plight.setColor((overhead_intensity, overhead_intensity, overhead_intensity, 1))
            plight.setShadowCaster(True, 1024, 1024)

            self.lights['overhead'][name] = self.render.attachNewNode(plight)
            self.lights['overhead'][name].setPos(self.table, x, y, z)
            self.render.setLight(self.lights['overhead'][name])

        add_overhead(0.5*w, 1.0*l, h, name='top')
        add_overhead(0.5*w, 0.5*l, h, name='middle')
        add_overhead(0.5*w, 0.0*l, h, name='bottom')

        ambient_intensity = 0.6
        alight = AmbientLight('alight')
        alight.setColor((ambient_intensity, ambient_intensity, ambient_intensity, 1))
        self.lights['ambient']['ambient1'] = self.render.attachNewNode(alight)
        self.render.setLight(self.lights['ambient']['ambient1'])

        self.render.setShaderAuto()


    def start(self):
        self.run()
