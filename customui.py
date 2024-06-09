from nicegui import ui, app
import os
import datetime
import tempfile
from astropy.io import fits
from PIL import Image
import shutil
import numpy as np
import plotly.graph_objs as go
import commsmanager

class SelectableListItem(ui.button):
    def get_readable_time_since_last_modified(self, timestamp):
        """Return a human-readable string representing the time since the file was last modified."""

        last_modified_time = datetime.datetime.fromtimestamp(timestamp)
        now = datetime.datetime.now()

        # Calculate the difference in time
        time_diff = now - last_modified_time

        # Determine the largest whole number time format
        seconds = time_diff.total_seconds()
        if seconds < 60:
            return f"{int(seconds)} seconds ago"
        minutes = seconds / 60
        if minutes < 60:
            return f"{int(minutes)} minutes ago"
        hours = minutes / 60
        if hours < 24:
            return f"{int(hours)} hours ago"
        days = hours / 24
        return f"{int(days)} days ago"

    def __init__(self, file, on_click=None, selected=False) -> None:
        super().__init__()
        self._state = False
        self.on('click', self.toggle)
        self.on_click = on_click
        self.file = file[0]
        #self.update()
        with self:
            ui.label(file[0]).classes('mr-auto')
            ui.label(self.get_readable_time_since_last_modified(file[1])).classes('ml-auto')
        
        if selected: #when refreshing the file browser, keep selected files selected
            self._state = True
            self.update()

    def toggle(self) -> None:
        """Toggle the button state."""
        self._state = not self._state
        self.update()
        if self._state and self.on_click is not None:
            self.on_click(self)

    def update(self) -> None:
        self.props(f'color={"grey-8" if self._state else "transparent"}')
        super().update()
    
    def is_clicked(self):
        return self._state

    def unclick(self):
        self._state = False
        self.update()


class FileBrowser(ui.list):

    def __init__(self, on_file_selected, *args,  **kwargs) -> None:
       
        super().__init__(*args,  **kwargs)
        
        self.directory="/Users/adampaul/Local Documents/Astrophotography/M106/Raw"
        
        self.clicked_file = None
        self.get_items_in_dir()

        self.on_file_selected = on_file_selected
        
    def set_dir(self, directory):
        if os.path.isdir(directory):
            self.directory = directory
            self.get_items_in_dir()

    def get_items_in_dir(self):
        # List all files in the directory
        self.clear()
        files = []
        self.items = []
        for entry in os.listdir(self.directory):
            # Join the directory path and entry name to get full path
            full_path = os.path.join(self.directory, entry)
            # Check if the entry is a file and add to list
            if os.path.isfile(full_path) and entry.endswith('.fits'):
                files.append((os.path.basename(entry), os.path.getmtime(full_path)))
        
        files.sort(key=lambda x: x[1], reverse=True)
        with self:
            ui.separator()
            for file in files:
                self.items.append(SelectableListItem(file, on_click=self.item_clicked, selected=self.clicked_file==file[0]).classes("w-full"))
                ui.separator()


    def item_clicked(self, item):
        self.clicked_file = item.file
        for element in self.items:
            if element != item and element.is_clicked():
                element.unclick()
        self.on_file_selected(os.path.join(self.directory, item.file))
        
        
    def add_item():
        print("item added")

class HeaterStateLabel(ui.label):
    def __init__(self):
        super().__init__("OFF")
    
    def update_text(self, driver_state: commsmanager.GenericControllerState, manual_state: commsmanager.GenericControllerState, real_state: commsmanager.HeaterState):
        driver_state = commsmanager.GenericControllerState(driver_state)
        manual_state = commsmanager.GenericControllerState(manual_state)
        real_state = commsmanager.HeaterState(real_state)
        if manual_state == commsmanager.GenericControllerState.STATE_ON:
            self.text = "On (Manual)"
        elif manual_state == commsmanager.GenericControllerState.STATE_OFF:
            self.text = "Off (Manual)"
        else:
            if driver_state == commsmanager.GenericControllerState.STATE_ON:
                if real_state == commsmanager.HeaterState.STATE_ON:
                    self.text = "Heating"
                if real_state == commsmanager.HeaterState.STATE_OFF:
                    self.text = "Cooling"
            else:
                self.text = "Off"
        self.update()

class LensCapStateLabel(ui.label):
    def __init__(self):
        super().__init__("Closed")
    
    def update_text(self, driver_state: commsmanager.GenericControllerState, manual_state: commsmanager.GenericControllerState, real_state: commsmanager.GenericControllerState):
        driver_state = commsmanager.GenericControllerState(driver_state)
        manual_state = commsmanager.GenericControllerState(manual_state)
        real_state = commsmanager.GenericControllerState(real_state)
        if manual_state == commsmanager.GenericControllerState.STATE_ON:
            self.text = "Open (Manual)"
        elif manual_state == commsmanager.GenericControllerState.STATE_OFF:
            self.text = "Closed (Manual)"
        else:
            if real_state == commsmanager.GenericControllerState.STATE_ON:
                self.text = "Open"
            else:
                self.text = "Closed"
        self.update()

class FlatLightLabel(ui.label):
    def __init__(self):
        super().__init__("Off")
    
    def update_text(self, driver_state: commsmanager.GenericControllerState, manual_state: commsmanager.GenericControllerState, real_state: commsmanager.GenericControllerState):
        driver_state = commsmanager.GenericControllerState(driver_state)
        manual_state = commsmanager.GenericControllerState(manual_state)
        real_state = commsmanager.GenericControllerState(real_state)
        if manual_state == commsmanager.GenericControllerState.STATE_ON:
            self.text = "On (Manual)"
        elif manual_state == commsmanager.GenericControllerState.STATE_OFF:
            self.text = "Off (Manual)"
        else:
            if real_state == commsmanager.GenericControllerState.STATE_ON:
                self.text = "On"
            else:
                self.text = "Off"
        self.update()


class Plot(ui.plotly):
    def __init__(self, series_labels):
        self.temperature_graph = go.Figure()
        self.x_data = []
        self.y_data = []
        for i, label in enumerate(series_labels):
            self.y_data.append([])
             # Adding the trace
            self.temperature_graph.add_trace(go.Scatter(x=self.x_data, y=self.y_data[i], mode='lines', name=label))
       

        # Updating the layout to set the background color to transparent
        self.temperature_graph.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',  # Transparent paper background
            plot_bgcolor='rgba(0,0,0,0)',   # Transparent plot background
            margin=dict(t=0, l=10, r=10, b=10),  # Remove top margin, adjust others as needed
            height=400,
            legend=dict(
                font=dict(color='white'),  # Legend items font color
                bgcolor='rgba(0,0,0,0)',  # Transparent legend background
                orientation='h',  # Horizontal legend orientation
                x=0.5,  # Center the legend horizontally
                y=1,  # Position the legend below the plot
                xanchor='center',  # Anchor legend position to center horizontally
                yanchor='bottom'  # Anchor legend position to the top
            ),

            xaxis=dict(
                title='Time', 
                title_font=dict(color='white'),  # Axis title font color
                tickfont=dict(color='white'),    # Axis tick font color
                gridcolor='grey'  # Grid line color
            ),
                yaxis=dict(
                title='Temperature (C)', 
                title_font=dict(color='white'),  # Axis title font color
                tickfont=dict(color='white'),    # Axis tick font color
                gridcolor='grey'  # Grid line color
            )
        )
        super().__init__(self.temperature_graph)
        # Display the plot using NiceGUI
    
    def update_series(self, data):
        if len(self.x_data) == 0:
            self.x_data.append(0)
        else:
            self.x_data.append(self.x_data[-1]+1)
        
        for idx, point in enumerate(data):
            self.y_data[idx].append(point)

        if len(self.x_data) > 50:
            for idx, element in enumerate(self.y_data):
                self.y_data[idx].pop(0)
            self.x_data.pop(0)

        for idx, element in enumerate(self.y_data):
            self.temperature_graph.data[idx].x = self.x_data
            self.temperature_graph.data[idx].y = element

        self.update()


class FITSViewer(ui.image):
    def __init__(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.last_converted = None
        self.converted_path = os.path.join(self.tmpdir.name, "converted.png")
        self.create_placeholder_img()
        super().__init__(self.converted_path)

    def set_image(self, image_path):
        if self.last_converted == image_path:
            return
        else:
            self.convert_fits_to_png(image_path)
            self.last_converted = image_path
            self.force_reload()
        pass

    def create_placeholder_img(self):
        # Create a blank white image
        image = Image.new("RGB", (900, int(900*0.6667)), color="white")
        
        # Save the image to the specified directory with the given filename
        image.save(self.converted_path)

    def convert_fits_to_png(self, fits_image_path):
        # Load the FITS file
        with fits.open(fits_image_path) as hdul:
            image_data = hdul[0].data

        image_data = np.nan_to_num(image_data)

        # Calculate the histogram of the image data
        histogram, bin_edges = np.histogram(image_data.flatten(), bins='auto', density=True)

        # Compute cumulative distribution from the histogram
        cdf = histogram.cumsum()
        cdf_normalized = cdf / cdf[-1]  # Normalize

        # Determine clipping points (e.g., 0.25% and 99.75%)
        cdf_min = np.searchsorted(cdf_normalized, 0.0025)
        cdf_max = np.searchsorted(cdf_normalized, 0.9975)

        # Clip the image data to these points and scale to 0-255
        clipped_data = np.clip(image_data, bin_edges[cdf_min], bin_edges[cdf_max])
        scaled_data = (clipped_data - bin_edges[cdf_min]) / (bin_edges[cdf_max] - bin_edges[cdf_min]) * 255
        image_uint8 = scaled_data.astype(np.uint8)

        # Convert to PIL image
        image = Image.fromarray(image_uint8)

        original_width, original_height = image.size
        
        # New width
        new_width = 900
        
        # Calculate the new height maintaining the aspect ratio
        new_height = int(new_width * original_height / original_width)
        
        # Resize the image
        resized_img = image.resize((new_width, new_height), Image.LANCZOS)

        
        # Save the image as PNG
        resized_img.save(self.converted_path, 'PNG')
        self.force_reload()


        return True

