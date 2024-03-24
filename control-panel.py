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

    def __init__(self,  *args, on_click=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._state = False
        self.on_click_callback = on_click
        self.on('click', self.toggle)

    def toggle(self) -> None:
        """Toggle the button state."""
        self._state = not self._state
        self.update()
        if self.on_click_callback:  # Check if the custom callback is provided
            self.on_click_callback()  # Call the custom callback

    def update(self) -> None:
        self.props(f'color={"light-blue-10" if self._state else "primary"}')
        super().update()

@dataclass
class RoofTelemUI:
    h_bridge_current_label: ui.label = ui.label('')
    voltage_5v_label: ui.label = ui.label('')
    voltage_12v_label: ui.label = ui.label('')
    raise_1_sw_label: ui.label = ui.label('')
    raise_2_sw_label: ui.label = ui.label('')
    lower_1_sw_label: ui.label = ui.label('')
    lower_2_sw_label: ui.label = ui.label('')

@dataclass
class RoofControlUI:
    enable_roof_control_sw: ui.switch
    raise_roof_btn: ToggleButton
    stop_roof_btn: ui.button
    lower_roof_btn: ToggleButton
    engage_lock_btn: ToggleButton
    stop_lock_btn: ui.button
    disengage_lock_btn: ToggleButton

def set_roof_buttons_state(roof_ui: RoofControlUI):
    if not roof_ui.enable_roof_control_sw.value:
        roof_ui.raise_roof_btn.disable()
        roof_ui.stop_roof_btn.disable()
        roof_ui.lower_roof_btn.disable()
        roof_ui.engage_lock_btn.disable()
        roof_ui.stop_lock_btn.disable()
        roof_ui.disengage_lock_btn.disable()
    else:
        #TODO
        pass


def raise_roof(roof_ui: RoofControlUI):
    set_roof_buttons_state(roof_ui)

def update_telemetry(ui):
    roof_telem = roof_manager.get_telemetry()
    ui.voltage_12v_label.text = format_voltage(roof_telem.voltage_12v)
    ui.h_bridge_current_label.text = format_current(roof_telem.h_bridge_current)
    ui.voltage_5v_label.text = format_voltage(roof_telem.voltage_5v)
    ui.raise_1_sw_label.text = format_limit_sw(roof_telem.raise_1_sw)
    ui.raise_2_sw_label.text = format_limit_sw(roof_telem.raise_2_sw)
    ui.lower_1_sw_label.text = format_limit_sw(roof_telem.lower_1_sw)
    ui.lower_2_sw_label.text = format_limit_sw(roof_telem.lower_2_sw)
    set_roof_connected(roof_manager.connected)

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
                    roof_control_sw = ui.switch('Enable Roof Control', on_change=(lambda: set_roof_buttons_state(self.roof_control_ui)))
                    with ui.row().classes('w-full justify-between'):
                        ui.label('Roof Position')
                        ui.label('CLOSED')
                    with ui.row().classes('w-full'):
                        roof_raise_btn = ToggleButton('Raise', on_click=(lambda: raise_roof(self.roof_control_ui))).classes('flex-grow')
                        roof_stop_btn = ui.button('Stop').classes('flex-grow')
                        roof_lower_btn = ui.button('Lower').classes('flex-grow')
                    with ui.row().classes('w-full justify-between'):
                        ui.label('Lock Position')
                        ui.label('ENGAGED')
                    with ui.row():
                        lock_engage_btn = ui.button('Engage')
                        lock_stop_btn = ui.button('Stop')
                        lock_disengage_btn = ui.button('Disengage')
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
        self.roof_control_ui = RoofControlUI(enable_roof_control_sw=roof_control_sw, raise_roof_btn=roof_raise_btn, stop_roof_btn=roof_stop_btn, lower_roof_btn=roof_lower_btn, engage_lock_btn=lock_engage_btn, stop_lock_btn=lock_stop_btn, disengage_lock_btn=lock_disengage_btn)

roof_manager = commsmanager.RoofCommManager("/dev/tty.usbmodem143201")

def format_voltage(voltage: str):
    if not roof_manager.connected: return "???"
    else: return format(voltage, '0.2f') + "V"
def format_current(current: str):
    if not roof_manager.connected: return "???"
    else: return format(current, '0.2f') + "A"
def format_limit_sw(sw: str):
    if not roof_manager.connected: return "???"
    else: return "HIGH" if sw == "true" else "LOW"



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
