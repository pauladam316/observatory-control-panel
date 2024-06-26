from nicegui import Client, app, core, run, ui
import time
from fastapi import Response
import base64
import cv2
import numpy as np
import serial
from fastapi_utils.tasks import repeat_every
import struct
#import videomanager
import commsmanager
from dataclasses import dataclass
import capturemanager
import customui
import plotly.graph_objs as go
import asyncio

dev_mode = True
sky_cam_latest_path = "/Users/adampaul/latest.jpg" #"/var/www/html/allsky/images/latest.jpg" 

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
    
def update_latest_photo(recent_image: ui.image):
    changed = capturemanager.convert_fits_to_png()
    if changed:
        recent_image.force_reload() 

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
    disable_roof_control()

def stop_lock(roof_ui: RoofControlUI):
    roof_ui.engage_lock_btn.button.turn_off()
    roof_ui.disengage_lock_btn.button.turn_off()
    roof_manager.stop_lock()
    disable_roof_control()

def update_telemetry(ui: RoofTelemUI):
    telescope_manager.get_telemetry()
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

def disable_roof_control():
    web_ui.roof_control_ui.enable_roof_control_sw.value = False

roof_manager = commsmanager.RoofCommManager("/dev/tty.usbmodem142201")
telescope_manager = commsmanager.TelescopeCommManager("/dev/tty.usbserial-B0004EQV")

class UI:
    def __init__(self):
        dark = ui.dark_mode()
        dark.enable()
        self.roof_telem_ui = RoofTelemUI()
        self.roof_control_ui = None
        self.temperature_graph = None
        with ui.card().style('align-self: center; width: fit-content;'):
            with ui.row().classes('w-full h-full justify-center'):
                with ui.column():
                    with ui.card().classes('justify-center'):
                                ui.label("Observatory Camera")
                                #observatory_video = ui.interactive_image()
                                #ui.timer(interval=0.1, callback=lambda: observatory_video.set_source(f'/video/frame/observatory_cam?{time.time()}'))
                    with ui.row().classes('w-full'):
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
                                    ui.label('Outside Temperature')
                                    ui.label('1°C')
                                with ui.row().classes('w-full justify-between'):
                                    ui.label('Humidity')
                                    ui.label('80%')
                           
                        with ui.column().classes('flex-grow'):
                            with ui.card().classes('w-full justify-center'):
                                ui.switch('Lens Cap', on_change=(lambda e: telescope_manager.send_command(commsmanager.TelescopeCommand.LENS_CAP_OPEN if e.value == 1 else commsmanager.TelescopeCommand.LENS_CAP_CLOSE)))
                                with ui.row().classes('w-full justify-between'):
                                    ui.label('State:')
                                    lens_cap_state = customui.LensCapStateLabel()
                                    ui.timer(0.1, callback=lambda: lens_cap_state.update_text(telescope_manager.last_data.lens_cap_driver_state, telescope_manager.last_data.lens_cap_manual_state, telescope_manager.last_data.lens_cap_real_state))
                            with ui.card().classes('w-full justify-center'):
                                ui.switch('Flat Light', on_change=(lambda e: telescope_manager.send_command(commsmanager.TelescopeCommand.LIGHT_ON if e.value == 1 else commsmanager.TelescopeCommand.LIGHT_OFF)))
                                with ui.row().classes('w-full justify-between'):
                                    ui.label('State:')
                                    lens_cap_state = customui.FlatLightLabel()
                                    ui.timer(0.1, callback=lambda: lens_cap_state.update_text(telescope_manager.last_data.flat_light_driver_state, telescope_manager.last_data.flat_light_manual_state, telescope_manager.last_data.flat_light_real_state))
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
                            
                with ui.column():
                    with ui.row():
                        with ui.column():
                            with ui.card().classes('justify-center'):
                                ui.label("Image Viewer")
                                recent_image = customui.FITSViewer().props(f"width=900px") #ui.image(capturemanager.converted_path).props(f"width=900px")
                                # if not dev_mode:
                                #     ui.timer(interval=1, callback=lambda: update_latest_photo(recent_image))
                            with ui.card().classes('w-full'):
                                with ui.row().classes('w-full'):
                                    with ui.column().classes('w-1/2 justify-center'):
                                        ui.label("File Browser")
                                        
                                        with ui.scroll_area().classes('w-full'):
                                            browser = customui.FileBrowser(on_file_selected=recent_image.convert_fits_to_png).props('dense separator').classes('w-full')
                                            ui.timer(interval=2, callback=browser.get_items_in_dir)
                                    with ui.column().classes('flex-grow justify-center h-full'):
                                        ui.input("Server Image Path", 
                                                value=browser.directory,
                                                on_change=lambda e: browser.set_dir(e.value)).classes('w-full')
                                        with ui.row().classes('w-full'):
                                            ui.switch("Show Most Recent")
                                      
                        with ui.column():
                            with ui.card().classes('justify-center'):
                                ui.label("Sky View")
                                sky_view = ui.image(sky_cam_latest_path).props(f"width=800px")
                                if not dev_mode:
                                    ui.timer(interval=30, callback=lambda: sky_view.force_reload())
                            with ui.row().classes('w-full'):
                                with ui.card().classes('w-full'):
                                    with ui.row().classes('w-full'):
                                        with ui.column().classes('w-1/4 justify-center'):
                                            ui.label('Heaters')
                                            with ui.card().classes("w-full"):
                                                ui.switch('Primary', on_change=(lambda e: telescope_manager.send_command(commsmanager.TelescopeCommand.HEATER_1_ENABLE if e.value == 1 else commsmanager.TelescopeCommand.HEATER_1_DISABLE)))
                                                with ui.row().classes('w-full justify-between'):
                                                    ui.label('State:')
                                                    heater_1_state = customui.HeaterStateLabel()
                                                    ui.timer(0.1, callback=lambda: heater_1_state.update_text(telescope_manager.last_data.heater_1_driver_state, telescope_manager.last_data.heater_1_manual_state, telescope_manager.last_data.heater_1_real_state))
                                            with ui.card().classes("w-full"):
                                                ui.switch('Secondary', on_change=(lambda e: telescope_manager.send_command(commsmanager.TelescopeCommand.HEATER_2_ENABLE if e.value == 1 else commsmanager.TelescopeCommand.HEATER_2_DISABLE)))
                                                with ui.row().classes('w-full justify-between'):
                                                    ui.label('State:')
                                                    heater_2_state = customui.HeaterStateLabel()
                                                    ui.timer(0.1, callback=lambda: heater_2_state.update_text(telescope_manager.last_data.heater_2_driver_state, telescope_manager.last_data.heater_2_manual_state, telescope_manager.last_data.heater_2_real_state))
                                            with ui.card().classes("w-full"):
                                                ui.switch('Guidescope', on_change=(lambda e: telescope_manager.send_command(commsmanager.TelescopeCommand.HEATER_3_ENABLE if e.value == 1 else commsmanager.TelescopeCommand.HEATER_3_DISABLE)))
                                                with ui.row().classes('w-full justify-between'):
                                                    ui.label('State:')
                                                    heater_3_state = customui.HeaterStateLabel()
                                                    ui.timer(0.1, callback=lambda: heater_3_state.update_text(telescope_manager.last_data.heater_3_driver_state, telescope_manager.last_data.heater_3_manual_state, telescope_manager.last_data.heater_3_real_state))
                                        temp_plot = customui.Plot(["Ambient", "Primary Mirror"]).classes("flex-grow")
                                        ui.timer(1.0, callback=lambda: temp_plot.update_series([telescope_manager.last_data.temp_ref, telescope_manager.last_data.temp_1]))
                        #ui.timer(interval=1, callback=lambda: update_latest_photo(recent_image))
                        #ui.label("Sky Camera")
                    #self.sky_video = ui.interactive_image().classes('w-full h-full')
                    #ui.timer(interval=0.1, callback=lambda: self.sky_video.set_source(f'/video/frame?{time.time()}'))

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

        roof_manager.on_raised(disable_roof_control)
        roof_manager.on_lowered(disable_roof_control)
        roof_manager.on_locked(disable_roof_control)
        roof_manager.on_unlocked(disable_roof_control)
    




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
