from nicegui import Client, app, core, run, ui
import time
from fastapi import Response
import base64
import cv2
import numpy as np
import serial
from fastapi_utils.tasks import repeat_every
import struct
import videomanager
import commsmanager
from dataclasses import dataclass



class ToggleButton(ui.button):

    def __init__(self,  *args, on_toggle_on=None, on_toggle_off=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._state = False
        self.on_toggle_on = on_toggle_on
        self.on_toggle_off = on_toggle_off
        self.on('click', self.toggle)

    def toggle(self) -> None:
        """Toggle the button state."""
        self._state = not self._state
        self.update()
        if self._state and self.on_toggle_on:
            self.on_toggle_on()
        elif not self._state and self.on_toggle_off:
            self.on_toggle_off()

    def turn_off(self) -> None:
        self._state = False
        self.update()

    def turn_on(self) -> None:
        self._state = True
        self.update()

    def update(self) -> None:
        self.props(f'color={"light-blue-10" if self._state else "primary"}')
        super().update()

    def disable(self):
        if self._state:
            self.turn_off()
        super().disable()

class ButtonConditions():
    def __init__(self, button: ui.button):
        self.button = button
        self.conditions = []

    def add_condition(self, condition):
        self.conditions.append(condition)

    def set_enabled(self):
        found = False
        for condition in self.conditions:
            if not condition():
                found = True
                if self.button.enabled:
                    self.button.disable()
                break
        if not found and not self.button.enabled:
            self.button.enable()
@dataclass
class RoofTelemUI:
    h_bridge_current_label: ui.label = ui.label('')
    voltage_5v_label: ui.label = ui.label('')
    voltage_12v_label: ui.label = ui.label('')
    raise_1_sw_label: ui.label = ui.label('')
    raise_2_sw_label: ui.label = ui.label('')
    lower_1_sw_label: ui.label = ui.label('')
    lower_2_sw_label: ui.label = ui.label('')
    roof_position_label: ui.label = ui.label('')
    lock_position_label: ui.label = ui.label('')

@dataclass
class RoofControlUI:
    enable_roof_control_sw: ui.switch
    raise_roof_btn: ButtonConditions
    stop_roof_btn: ButtonConditions
    lower_roof_btn: ButtonConditions
    engage_lock_btn: ButtonConditions
    stop_lock_btn: ButtonConditions
    disengage_lock_btn: ButtonConditions

def reset_roof_motion(roof_ui: RoofControlUI):
    roof_ui.raise_roof_btn.button.turn_off()
    roof_ui.lower_roof_btn.button.turn_off()
    roof_manager.send_command(commsmanager.RoofCommand.CMD_STOP_ROOF)

def set_roof_buttons_state(roof_ui: RoofControlUI):
    if not roof_manager.connected:
        stop_roof(roof_ui)
    roof_ui.raise_roof_btn.set_enabled()
    roof_ui.stop_roof_btn.set_enabled()
    roof_ui.lower_roof_btn.set_enabled()
    roof_ui.engage_lock_btn.set_enabled()
    roof_ui.stop_lock_btn.set_enabled()
    roof_ui.disengage_lock_btn.set_enabled()
    

# #TODO: control buttons based on state machine
# def control_roof(roof_ui: RoofControlUI):
#     if roof_ui.raise_roof_btn.button._state == True and roof_ui.lower_roof_btn.button._state == True:
#         roof_ui.raise_roof_btn.button.turn_off()
#         roof_ui.lower_roof_btn.button.turn_off()
#         roof_manager.send_command(commsmanager.RoofCommand.CMD_STOP_ROOF)
#         roof_ui.enable_roof_control_sw.value = False
#     elif roof_ui.raise_roof_btn.button._state == True:
#         roof_manager.send_command(commsmanager.RoofCommand.CMD_RAISE_ROOF)
#     elif roof_ui.lower_roof_btn.button._state == True:
#         roof_manager.send_command(commsmanager.RoofCommand.CMD_LOWER_ROOF)
#     else:
#         roof_manager.send_command(commsmanager.RoofCommand.CMD_STOP_ROOF)
#         roof_ui.enable_roof_control_sw.value = False

def stop_roof(roof_ui: RoofControlUI):
    roof_ui.raise_roof_btn.button.turn_off()
    roof_ui.lower_roof_btn.button.turn_off()
    roof_manager.stop_roof()
    roof_ui.enable_roof_control_sw.value = False

def stop_lock(roof_ui: RoofControlUI):
    roof_ui.engage_lock_btn.button.turn_off()
    roof_ui.disengage_lock_btn.button.turn_off()
    roof_manager.stop_lock()
    roof_ui.enable_roof_control_sw.value = False

def update_telemetry(ui: RoofTelemUI):
    last_telemetry = roof_manager.get_telemetry()
    ui.voltage_12v_label.text = format_voltage(last_telemetry.voltage_12v)
    ui.h_bridge_current_label.text = format_current(last_telemetry.h_bridge_current)
    ui.voltage_5v_label.text = format_voltage(last_telemetry.voltage_5v)
    ui.raise_1_sw_label.text = format_limit_sw(last_telemetry.raise_1_sw)
    ui.raise_2_sw_label.text = format_limit_sw(last_telemetry.raise_2_sw)
    ui.lower_1_sw_label.text = format_limit_sw(last_telemetry.lower_1_sw)
    ui.lower_2_sw_label.text = format_limit_sw(last_telemetry.lower_2_sw)
    ui.roof_position_label.text = format_motion_state(last_telemetry.roof_state)
    ui.lock_position_label.text = format_motion_state(last_telemetry.lock_state)
    set_roof_connected(roof_manager.connected)



roof_manager = commsmanager.RoofCommManager("/dev/tty.usbmodem141201")

class UI:
    def __init__(self):
        self.roof_telem_ui = RoofTelemUI()
        self.roof_control_ui = None
        with ui.row().classes('w-full h-full justify-center'):
            with ui.column():
                with ui.card().classes('w-full justify-center'):
                    with ui.row().classes('w-full justify-between'):
                        ui.label('Roof Controller')
                        self.roof_connected = ui.label()
                    with ui.row().classes('w-full justify-between'):
                        ui.label('Telescope Controller')
                        ui.label('CONNECTED')
                with ui.card().classes('w-full justify-center'):
                    roof_control_sw = ui.switch('Enable Roof Control', on_change=(lambda: reset_roof_motion(self.roof_control_ui)))
                    with ui.row().classes('w-full justify-between'):
                        ui.label('Roof Position')
                        self.roof_telem_ui.roof_position_label = ui.label('')
                    with ui.row().classes('w-full'):
                        roof_raise_btn = ToggleButton('Raise', on_toggle_on=(lambda: roof_manager.raise_roof()), on_toggle_off=(lambda: stop_roof(self.roof_control_ui))).classes('flex-grow')
                        roof_stop_btn = ui.button('Stop', on_click=(lambda: stop_roof(self.roof_control_ui))).classes('flex-grow')
                        roof_lower_btn = ToggleButton('Lower', on_toggle_on=(lambda: roof_manager.lower_roof()), on_toggle_off=(lambda: stop_roof(self.roof_control_ui))).classes('flex-grow')
                    with ui.row().classes('w-full justify-between'):
                        ui.label('Lock Position')
                        self.roof_telem_ui.lock_position_label = ui.label('')
                    with ui.row():
                        lock_engage_btn = ToggleButton('Engage', on_toggle_on=(lambda: roof_manager.engage_lock()), on_toggle_off=(lambda: stop_lock(self.roof_control_ui))).classes('flex-grow')
                        lock_stop_btn = ui.button('Stop',  on_click=(lambda: stop_lock(self.roof_control_ui)))
                        lock_disengage_btn = ToggleButton('Disengage', on_toggle_on=(lambda: roof_manager.disengage_lock()), on_toggle_off=(lambda: stop_lock(self.roof_control_ui))).classes('flex-grow')
                with ui.card().classes('w-full justify-center'):
                    with ui.row().classes('w-full justify-between'):
                        ui.label('Lens Cap Position')
                        ui.label('CLOSED')
                    with ui.row().classes('w-full'):
                        ui.button('Open').classes('flex-grow')
                        ui.button('Stop').classes('flex-grow')
                        ui.button('Close').classes('flex-grow')
                    switch = ui.switch('Flat Light')
            with ui.column():
                with ui.card().classes('w-full justify-center'):
                    with ui.row().classes('w-full justify-between'):
                        ui.label('Outside Temperature')
                        ui.label('1°C')
                    with ui.row().classes('w-full justify-between'):
                        ui.label('Humidity')
                        ui.label('80%')
                with ui.card().classes('w-full justify-center'):
                    switch = ui.switch('Primary Mirror Heater').classes('flex-grow')
                    with ui.row().classes('w-full justify-between'):
                        ui.label('Temperature')
                        ui.label('3°C')
                    with ui.row().classes('w-full'):
                        ui.number(label='Setpoint').classes('flex-grow')
                with ui.card().classes('w-full justify-center'):
                    switch = ui.switch('Secondary Mirror Heater').classes('flex-grow')
                    with ui.row().classes('w-full justify-between'):
                        ui.label('Temperature')
                        ui.label('3°C')
                    with ui.row().classes('w-full'):
                        ui.number(label='Setpoint').classes('flex-grow')
                with ui.card().classes('w-full justify-center'):
                    switch = ui.switch('Guidescope Heater').classes('flex-grow')
                    with ui.row().classes('w-full justify-between'):
                        ui.label('Temperature')
                        ui.label('3°C')
                    with ui.row().classes('w-full'):
                        ui.number(label='Setpoint').classes('flex-grow')
            
            with ui.column():
                with ui.card().classes('w-full justify-center'):
                    ui.label("Most Recent Image")
                    ui.image('https://picsum.photos/id/377/640/360')
                with ui.card().classes('w-full justify-center'):
                    ui.label("Observatory Camera")
                    observatory_video = ui.interactive_image().classes('w-full h-full')
                    ui.timer(interval=0.1, callback=lambda: observatory_video.set_source(f'/video/frame/observatory_cam?{time.time()}'))

                    #ui.label("Sky Camera")
                #self.sky_video = ui.interactive_image().classes('w-full h-full')
                #ui.timer(interval=0.1, callback=lambda: self.sky_video.set_source(f'/video/frame?{time.time()}'))
            
            with ui.column():
                with ui.card().classes('w-full justify-center'):
                    ui.label("Roof Control Debug Menu")
                    with ui.row().classes('w-full justify-between'):
                        ui.label('12V Voltage')
                        self.roof_telem_ui.voltage_12v_label = ui.label('')
                    with ui.row().classes('w-full justify-between'):
                        ui.label('5V Voltage')
                        self.roof_telem_ui.voltage_5v_label = ui.label('')
                    with ui.row().classes('w-full justify-between'):
                        ui.label('H-Bridge Current')
                        self.roof_telem_ui.h_bridge_current_label = ui.label('')
                    with ui.row().classes('w-full justify-between'):
                        ui.label('U1 Position')
                        self.roof_telem_ui.raise_1_sw_label = ui.label()
                    with ui.row().classes('w-full justify-between'):
                        ui.label('U2 Position')
                        self.roof_telem_ui.raise_2_sw_label = ui.label()
                    with ui.row().classes('w-full justify-between'):
                        ui.label('L1 Position')
                        self.roof_telem_ui.lower_1_sw_label = ui.label()
                    with ui.row().classes('w-full justify-between'):
                        ui.label('L2 Position')
                        self.roof_telem_ui.lower_2_sw_label = ui.label()
        ui.timer(0.1, callback=lambda: update_telemetry(self.roof_telem_ui))
        ui.timer(0.1, callback=lambda: roof_manager.update())
        
        self.roof_control_ui = RoofControlUI(enable_roof_control_sw=roof_control_sw, raise_roof_btn=ButtonConditions(roof_raise_btn), stop_roof_btn=ButtonConditions(roof_stop_btn), lower_roof_btn=ButtonConditions(roof_lower_btn), engage_lock_btn=ButtonConditions(lock_engage_btn), stop_lock_btn=ButtonConditions(lock_stop_btn), disengage_lock_btn=ButtonConditions(lock_disengage_btn))
        self.roof_control_ui.raise_roof_btn.add_condition(lambda: self.roof_control_ui.enable_roof_control_sw.value)
        self.roof_control_ui.raise_roof_btn.add_condition(lambda: roof_manager.last_data.roof_state != commsmanager.MotionState.RAISED)
        self.roof_control_ui.raise_roof_btn.add_condition(lambda: roof_manager.last_data.roof_state != commsmanager.MotionState.LOWERING)
        self.roof_control_ui.raise_roof_btn.add_condition(lambda: roof_manager.last_data.lock_state == commsmanager.MotionState.LOWERED or roof_manager.last_data.lock_state == commsmanager.MotionState.UNKNOWN)
 
        #self.roof_control_ui.stop_roof_btn.add_condition(lambda: self.roof_control_ui.enable_roof_control_sw.value)

        self.roof_control_ui.lower_roof_btn.add_condition(lambda: self.roof_control_ui.enable_roof_control_sw.value)
        self.roof_control_ui.lower_roof_btn.add_condition(lambda: roof_manager.last_data.roof_state != commsmanager.MotionState.LOWERED)
        self.roof_control_ui.lower_roof_btn.add_condition(lambda: roof_manager.last_data.roof_state != commsmanager.MotionState.RAISING)
        self.roof_control_ui.lower_roof_btn.add_condition(lambda: roof_manager.last_data.lock_state == commsmanager.MotionState.LOWERED or roof_manager.last_data.lock_state == commsmanager.MotionState.UNKNOWN)

        self.roof_control_ui.engage_lock_btn.add_condition(lambda: self.roof_control_ui.enable_roof_control_sw.value)
        self.roof_control_ui.engage_lock_btn.add_condition(lambda: roof_manager.last_data.lock_state != commsmanager.MotionState.RAISED)
        self.roof_control_ui.engage_lock_btn.add_condition(lambda: roof_manager.last_data.lock_state != commsmanager.MotionState.LOWERING)

        #self.roof_control_ui.stop_lock_btn.add_condition(lambda: self.roof_control_ui.enable_roof_control_sw.value)

        self.roof_control_ui.disengage_lock_btn.add_condition(lambda: self.roof_control_ui.enable_roof_control_sw.value)
        self.roof_control_ui.disengage_lock_btn.add_condition(lambda: roof_manager.last_data.lock_state != commsmanager.MotionState.LOWERED)
        self.roof_control_ui.disengage_lock_btn.add_condition(lambda: roof_manager.last_data.lock_state != commsmanager.MotionState.RAISING)

        ui.timer(0.1, callback=lambda: set_roof_buttons_state(self.roof_control_ui))


def format_voltage(voltage):
    if not roof_manager.connected: return "???"
    else: return format(voltage, '0.2f') + "V"
def format_current(current):
    if not roof_manager.connected: return "???"
    else: return format(current, '0.2f') + "A"
def format_limit_sw(sw):
    if not roof_manager.connected: return "???"
    else: return "HIGH" if sw else "LOW"
def format_motion_state(state):
    if not roof_manager.connected: return "???"
    else: return commsmanager.MotionState(state).name

roof_port = None
NUM_TELEM_ELEMENTS=7

def set_roof_connected(connected: bool):
    global roof_port
    if connected:
        web_ui.roof_connected.text = "CONNECTED"
    else:
        web_ui.roof_connected.text = "DISCONNECTED"
        roof_port = None



web_ui = UI()
ui.run()
