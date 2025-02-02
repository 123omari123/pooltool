#! /usr/bin/env python

import pooltool.ani as ani
from pooltool.ani.action import Action
from pooltool.ani.modes.datatypes import BaseMode, Mode


class StrokeMode(BaseMode):
    name = Mode.stroke
    keymap = {
        Action.fine_control: False,
        Action.stroke: True,
    }

    def enter(self):
        self.mode_stroked_from = self.last_mode
        self.mouse.hide()
        self.mouse.relative()
        self.mouse.track()

        self.shots.active.cue.track_stroke()
        self.shots.active.cue.show_nodes(ignore=("cue_cseg",))

        self.task_action("f", Action.fine_control, True)
        self.task_action("f-up", Action.fine_control, False)
        self.task_action("s", Action.stroke, True)
        self.task_action("s-up", Action.stroke, False)

        self.add_task(self.stroke_task, "stroke_task")

    def exit(self):
        self.remove_task("stroke_task")
        self.player_cam.store_state(Mode.stroke, overwrite=True)

    def stroke_task(self, task):
        if self.keymap[Action.stroke]:
            if self.game.is_call_pocket and self.game.pocket_call is None:
                return task.cont
            if self.game.is_call_ball and self.game.ball_call is None:
                return task.cont

            if self.stroke_cue_stick():
                # The cue stick has contacted the cue ball
                self.shots.active.cue.set_object_state_as_render_state()
                self.shots.active.cue.strike()
                self.shots.active.user_stroke = True
                self.change_mode(Mode.calculate)
                return
        else:
            self.shots.active.cue.get_node("cue_stick").setX(0)
            self.shots.active.cue.hide_nodes(ignore=("cue_cseg",))
            self.change_mode(self.last_mode)
            return

        return task.cont

    def stroke_cue_stick(self):
        max_speed_mouse = ani.max_stroke_speed / ani.stroke_sensitivity  # [px/s]
        max_backstroke = self.shots.active.cue.length * ani.backstroke_fraction  # [m]

        with self.mouse:
            dt = self.mouse.get_dt()
            dx = self.mouse.get_dy()

        speed_mouse = dx / dt
        if speed_mouse > max_speed_mouse:
            dx *= max_speed_mouse / speed_mouse

        cue_stick_node = self.shots.active.cue.get_node("cue_stick")
        newX = min(max_backstroke, cue_stick_node.getX() - dx * ani.stroke_sensitivity)

        if newX < 0:
            newX = 0
            collision = True if self.shots.active.cue.is_shot() else False
        else:
            collision = False

        cue_stick_node.setX(newX)
        self.shots.active.cue.append_stroke_data()

        return True if collision else False
