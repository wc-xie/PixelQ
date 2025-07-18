#!/usr/bin/env python3
"""
PixelQ - LED Array Brightness Measurement Tool

A GUI application for measuring brightness of individual LEDs in an array from camera images.
Supports grid-based detection with editable corners and manual positioning.

Author: PixelQ Development Team
Version: 2.0
"""

import os
# Suppress Tkinter deprecation warning on macOS
os.environ['TK_SILENCE_DEPRECATION'] = '1'

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk
import json
import csv

class PixelQApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PixelQ - LED Array Brightness Measurement")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 600)  # Set minimum window size
        
        # Initialize variables
        self.original_image = None
        self.display_image = None
        self.photo = None
        self.canvas_width = 800
        self.canvas_height = 600
        self.scale_factor = 1.0
        
        # LED array parameters
        self.array_size = tk.IntVar(value=8)  # nxn grid
        self.grid_visible = tk.BooleanVar(value=True)
        self.grid_corners = []  # Four corners of the LED array
        self.led_positions = []  # Calculated LED positions
        
        # Drawing state
        self.drawing_grid = False
        self.grid_corner_count = 0
        self.manual_positioning = False
        self.manual_positions = {}  # Store manually positioned LEDs
        self.adjusting_pixels = False
        self.selected_led_index = None  # Track which LED is being adjusted
        self.detection_method = tk.StringVar(value="grid")  # Keep for compatibility
        
        # Undo/Redo system
        self.history = []  # Store states for undo
        self.redo_stack = []  # Store states for redo
        self.max_history = 20  # Maximum undo steps
        
        # Zoom functionality
        self.zoom_level = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 5.0
        self.zoom_step = 0.1
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the user interface"""
        # Create main container with simpler structure
        # Left panel for controls with scrollbar
        control_container = ttk.Frame(self.root, width=350)
        control_container.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        control_container.pack_propagate(False)
        
        # Create canvas and scrollbar for scrollable control panel
        self.control_canvas = tk.Canvas(control_container, width=280, highlightthickness=0, 
                                       bg='#f0f0f0', relief=tk.FLAT)
        control_scrollbar = ttk.Scrollbar(control_container, orient="vertical", command=self.control_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.control_canvas)
        
        # Configure scrolling
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.control_canvas.configure(scrollregion=self.control_canvas.bbox("all"))
        )
        
        # Create window in canvas for the scrollable frame
        self.control_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.control_canvas.configure(yscrollcommand=control_scrollbar.set)
        
        # Pack canvas and scrollbar
        self.control_canvas.pack(side="left", fill="both", expand=True)
        control_scrollbar.pack(side="right", fill="y")
        
        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            self.control_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _on_enter(event):
            # When mouse enters control panel, bind mousewheel
            self.control_canvas.bind_all("<MouseWheel>", _on_mousewheel)
            self.control_canvas.bind_all("<Button-4>", lambda e: self.control_canvas.yview_scroll(-1, "units"))
            self.control_canvas.bind_all("<Button-5>", lambda e: self.control_canvas.yview_scroll(1, "units"))
            
        def _on_leave(event):
            # When mouse leaves control panel, unbind mousewheel
            self.control_canvas.unbind_all("<MouseWheel>")
            self.control_canvas.unbind_all("<Button-4>")
            self.control_canvas.unbind_all("<Button-5>")
        
        # Bind enter/leave events for better mousewheel handling
        self.control_canvas.bind("<Enter>", _on_enter)
        self.control_canvas.bind("<Leave>", _on_leave)
        
        # Alternative: Bind mousewheel events directly (may work better on some systems)
        self.control_canvas.bind("<MouseWheel>", _on_mousewheel)  # Windows/Mac
        self.control_canvas.bind("<Button-4>", lambda e: self.control_canvas.yview_scroll(-1, "units"))  # Linux up
        self.control_canvas.bind("<Button-5>", lambda e: self.control_canvas.yview_scroll(1, "units"))   # Linux down
        
        # Right panel for canvas
        canvas_frame = ttk.Frame(self.root)
        canvas_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Setup control panel (now in scrollable frame)
        self.setup_control_panel(self.scrollable_frame)
        
        # Canvas for image display
        self.canvas = tk.Canvas(canvas_frame, width=self.canvas_width, height=self.canvas_height, 
                               bg='lightgray', cursor='crosshair', relief=tk.SUNKEN, bd=1)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bind canvas events
        self.canvas.bind("<Button-1>", self.canvas_click)
        self.canvas.bind("<B1-Motion>", self.canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.canvas_release)
        
        # Bind zoom events
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)  # Windows/Linux
        self.canvas.bind("<Button-4>", self.on_mousewheel)    # Linux
        self.canvas.bind("<Button-5>", self.on_mousewheel)    # Linux
        
        # Bind keyboard shortcuts
        self.root.bind("<Control-z>", self.undo)
        self.root.bind("<Control-y>", self.redo)
        self.root.bind("<Control-Z>", self.undo)  # Handle Shift+Ctrl+Z as undo too
        self.root.bind("<Control-Y>", self.redo)
        
        # Make root focusable for keyboard events
        self.root.focus_set()
        
        # Update scroll region after a short delay to ensure all widgets are rendered
        self.root.after(100, self.update_scroll_region)
        
    def update_scroll_region(self):
        """Update the scroll region of the control panel"""
        self.control_canvas.update_idletasks()
        self.control_canvas.configure(scrollregion=self.control_canvas.bbox("all"))
        
    def setup_control_panel(self, parent):
        """Setup the control panel with all controls"""
        # File operations
        file_frame = ttk.LabelFrame(parent, text="File Operations")
        file_frame.pack(fill=tk.X, pady=5, padx=5)
        
        ttk.Button(file_frame, text="Load Image", command=self.load_image).pack(fill=tk.X, pady=2, padx=5)
        ttk.Button(file_frame, text="Save Results", command=self.save_results).pack(fill=tk.X, pady=2, padx=5)
        
        # Zoom controls
        zoom_frame = ttk.LabelFrame(parent, text="Zoom Controls")
        zoom_frame.pack(fill=tk.X, pady=5, padx=5)
        
        zoom_buttons_frame = ttk.Frame(zoom_frame)
        zoom_buttons_frame.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Button(zoom_buttons_frame, text="Zoom In (+)", command=self.zoom_in).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_buttons_frame, text="Zoom Out (-)", command=self.zoom_out).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_buttons_frame, text="Reset Zoom", command=self.reset_zoom).pack(side=tk.LEFT, padx=2)
        
        # Zoom level display
        self.zoom_label = ttk.Label(zoom_frame, text="Zoom: 100%")
        self.zoom_label.pack(pady=2)
        
        # Undo/Redo controls
        history_frame = ttk.LabelFrame(parent, text="History (Ctrl+Z/Y)")
        history_frame.pack(fill=tk.X, pady=5, padx=5)
        
        history_buttons_frame = ttk.Frame(history_frame)
        history_buttons_frame.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Button(history_buttons_frame, text="Undo", command=lambda: self.undo(None)).pack(side=tk.LEFT, padx=2)
        ttk.Button(history_buttons_frame, text="Redo", command=lambda: self.redo(None)).pack(side=tk.LEFT, padx=2)
        
        # Array configuration
        array_frame = ttk.LabelFrame(parent, text="LED Array Configuration")
        array_frame.pack(fill=tk.X, pady=5, padx=5)
        
        ttk.Label(array_frame, text="Array Size (n×n):").pack(anchor=tk.W, padx=5)
        array_spinbox = ttk.Spinbox(array_frame, from_=2, to=200, textvariable=self.array_size, 
                                   command=self.update_grid, width=10)
        array_spinbox.pack(anchor=tk.W, pady=2, padx=5)
        
        ttk.Checkbutton(array_frame, text="Show Grid", variable=self.grid_visible, 
                       command=self.toggle_grid).pack(anchor=tk.W, pady=2, padx=5)
        
        # Detection & Alignment tools
        align_frame = ttk.LabelFrame(parent, text="Detection & Alignment")
        align_frame.pack(fill=tk.X, pady=5, padx=5)
        
        # Detection method selection
        ttk.Label(align_frame, text="Detection Method: Grid-based with editable corners").pack(anchor=tk.W, padx=5)
        
        # Separator
        ttk.Separator(align_frame, orient='horizontal').pack(fill=tk.X, padx=5, pady=5)
        
        # Alignment tools
        ttk.Button(align_frame, text="Define Grid Corners", 
                  command=self.start_grid_definition).pack(fill=tk.X, pady=1, padx=5)
        ttk.Button(align_frame, text="Edit Grid Corners", 
                  command=self.edit_grid_corners).pack(fill=tk.X, pady=1, padx=5)
        ttk.Button(align_frame, text="Clear All Detections", 
                  command=self.clear_all_detections).pack(fill=tk.X, pady=1, padx=5)
        
        # Measurement tools
        measure_frame = ttk.LabelFrame(parent, text="Measurement")
        measure_frame.pack(fill=tk.X, pady=5, padx=5)
        
        # Measurement method selection
        self.measurement_method = tk.StringVar(value="direct")
        ttk.Label(measure_frame, text="Measurement Method:").pack(anchor=tk.W, padx=5)
        
        method_frame = ttk.Frame(measure_frame)
        method_frame.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Radiobutton(method_frame, text="Direct Detection", variable=self.measurement_method, 
                       value="direct").pack(anchor=tk.W)
        ttk.Radiobutton(method_frame, text="Grid Interpolation", variable=self.measurement_method, 
                       value="interpolation").pack(anchor=tk.W)
        ttk.Radiobutton(method_frame, text="Manual Positioning", variable=self.measurement_method, 
                       value="manual").pack(anchor=tk.W)
        
        # Sampling area size
        sampling_frame = ttk.Frame(measure_frame)
        sampling_frame.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(sampling_frame, text="Sampling area:").pack(side=tk.LEFT)
        self.sampling_size = tk.IntVar(value=5)
        ttk.Spinbox(sampling_frame, from_=3, to=15, textvariable=self.sampling_size, 
                   width=5).pack(side=tk.LEFT, padx=5)
        ttk.Label(sampling_frame, text="pixels").pack(side=tk.LEFT)
        
        # Dark LED enhancement
        enhancement_frame = ttk.Frame(measure_frame)
        enhancement_frame.pack(fill=tk.X, padx=5, pady=2)
        
        self.enhance_dark_leds = tk.BooleanVar(value=True)
        ttk.Checkbutton(enhancement_frame, text="Enhance dark LEDs", 
                       variable=self.enhance_dark_leds).pack(anchor=tk.W)
        
        ttk.Button(measure_frame, text="Measure Brightness", 
                  command=self.measure_brightness).pack(fill=tk.X, pady=1, padx=5)
        ttk.Button(measure_frame, text="Manual Position Mode", 
                  command=self.start_manual_positioning).pack(fill=tk.X, pady=1, padx=5)
        ttk.Button(measure_frame, text="Adjust LED Positions", 
                  command=self.start_pixel_adjustment).pack(fill=tk.X, pady=1, padx=5)
        ttk.Button(measure_frame, text="Export to CSV", 
                  command=self.export_csv).pack(fill=tk.X, pady=1, padx=5)
        
        # Results display
        results_frame = ttk.LabelFrame(parent, text="Results")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=5)
        
        # Create treeview for results
        columns = ('ID', 'Row', 'Col', 'Brightness', 'R', 'G', 'B')
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=6)
        
        # Set column properties
        self.results_tree.heading('ID', text='LED#')
        self.results_tree.heading('Row', text='Row')
        self.results_tree.heading('Col', text='Col') 
        self.results_tree.heading('Brightness', text='Brightness')
        self.results_tree.heading('R', text='R')
        self.results_tree.heading('G', text='G')
        self.results_tree.heading('B', text='B')
        
        self.results_tree.column('ID', width=40)
        self.results_tree.column('Row', width=40)
        self.results_tree.column('Col', width=40)
        self.results_tree.column('Brightness', width=80)
        self.results_tree.column('R', width=40)
        self.results_tree.column('G', width=40)
        self.results_tree.column('B', width=40)
        
        # Scrollbar for results
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)
        
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2, pady=2)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=2)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(parent, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, pady=(10, 5), padx=5)
        
        # Add scroll hint at the bottom
        scroll_hint = ttk.Label(parent, text="💡 Use mouse wheel to scroll", 
                               font=('Arial', 8), foreground='gray')
        scroll_hint.pack(fill=tk.X, padx=5, pady=(0, 5))
        
    def load_image(self):
        """Load an image file"""
        file_path = filedialog.askopenfilename(
            title="Select Image",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                self.original_image = cv2.imread(file_path)
                if self.original_image is None:
                    raise ValueError("Could not load image")
                
                self.original_image = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2RGB)
                self.display_image_on_canvas()
                self.status_var.set(f"Image loaded: {os.path.basename(file_path)}")
                
                # Clear previous alignment data
                self.clear_all_detections()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load image: {str(e)}")
                

                
    def display_image_on_canvas(self):
        """Display the image on the canvas with proper scaling"""
        if self.original_image is None:
            return
            
        # Calculate scale factor to fit image in canvas
        h, w = self.original_image.shape[:2]
        scale_w = self.canvas_width / w
        scale_h = self.canvas_height / h
        self.scale_factor = min(scale_w, scale_h, 1.0)  # Don't upscale
        
        # Resize image for display
        new_w = int(w * self.scale_factor)
        new_h = int(h * self.scale_factor)
        self.display_image = cv2.resize(self.original_image, (new_w, new_h))
        
        # Convert to PIL Image and then to PhotoImage
        pil_image = Image.fromarray(self.display_image)
        self.photo = ImageTk.PhotoImage(pil_image)
        
        # Clear canvas and display image
        self.canvas.delete("all")
        self.canvas.create_image(self.canvas_width//2, self.canvas_height//2, 
                               image=self.photo, anchor=tk.CENTER)
        
        # Redraw overlays
        self.draw_grid_corners()
        if self.grid_visible.get():
            self.draw_led_grid()
            
    def canvas_click(self, event):
        """Handle canvas click events"""
        if self.drawing_grid and self.grid_corner_count < 4:
            self.grid_corners.append((event.x, event.y))
            self.grid_corner_count += 1
            self.draw_grid_corners()
            
            if self.grid_corner_count == 4:
                self.drawing_grid = False
                self.status_var.set("Grid corners defined. Calculate LED positions.")
                self.calculate_led_positions()
                self.save_state()  # Save state after defining corners
                
        elif hasattr(self, 'editing_corners') and self.editing_corners:
            # Check if clicking near an existing corner to edit it
            corner_index = self.find_nearest_corner(event.x, event.y)
            if corner_index is not None:
                self.grid_corners[corner_index] = (event.x, event.y)
                self.draw_grid_corners()
                self.calculate_led_positions()
                if self.grid_visible.get():
                    self.draw_led_grid()
                self.save_state()  # Save state after editing corner
                self.status_var.set(f"Updated corner {corner_index + 1} - Grid recalculated")
                
        elif self.adjusting_pixels:
            # Pixel adjustment mode - click to adjust LED positions
            self.handle_pixel_adjustment(event.x, event.y)
                
        elif self.manual_positioning:
            # Manual positioning mode - click to set LED positions
            self.handle_manual_positioning(event.x, event.y)
                
    def canvas_drag(self, event):
        """Handle canvas drag events"""
        pass  # No drag events needed without constraint lines
            
    def canvas_release(self, event):
        """Handle canvas release events"""
        pass  # No release events needed without constraint lines
            
    def start_grid_definition(self):
        """Start defining grid corners"""
        self.save_state()  # Save state before starting new definition
        self.drawing_grid = True
        self.grid_corner_count = 0
        self.grid_corners = []
        self.status_var.set("Click on 4 corners of the LED array (top-left, top-right, bottom-right, bottom-left)")
        
    def draw_grid_corners(self):
        """Draw grid corner markers"""
        self.canvas.delete('corners')
        for i, (x, y) in enumerate(self.grid_corners):
            # Use different colors based on editing mode
            if hasattr(self, 'editing_corners') and self.editing_corners:
                fill_color = 'orange'
                text_color = 'red'
                marker_text = f'C{i+1}'
            else:
                fill_color = 'blue'
                text_color = 'blue'
                marker_text = f'{i+1}'
                
            self.canvas.create_oval(x-6, y-6, x+6, y+6, fill=fill_color, outline='black', 
                                  width=2, tags='corners')
            self.canvas.create_text(x+12, y-12, text=marker_text, fill=text_color, 
                                  font=('Arial', 10, 'bold'), tags='corners')
            
    def calculate_led_positions(self):
        """Calculate LED positions based on grid corners"""
        if len(self.grid_corners) != 4:
            return
            
        # Order corners: top-left, top-right, bottom-right, bottom-left
        corners = np.array(self.grid_corners, dtype=np.float32)
        
        # Calculate LED positions in grid
        n = self.array_size.get()
        self.led_positions = []
        
        for row in range(n):
            for col in range(n):
                # Bilinear interpolation between corners
                u = col / (n - 1) if n > 1 else 0
                v = row / (n - 1) if n > 1 else 0
                
                # Interpolate between corners
                top = corners[0] * (1 - u) + corners[1] * u
                bottom = corners[3] * (1 - u) + corners[2] * u
                pos = top * (1 - v) + bottom * v
                
                self.led_positions.append((int(pos[0]), int(pos[1]), row, col))
                
    def draw_led_grid(self):
        """Draw LED grid overlay"""
        if not self.led_positions:
            return
            
        for x, y, row, col in self.led_positions:
            # Draw LED position marker
            self.canvas.create_oval(x-3, y-3, x+3, y+3, fill='green', outline='darkgreen', tags='led_grid')
            # Draw LED number
            self.canvas.create_text(x+8, y-8, text=f'{row},{col}', fill='green', font=('Arial', 8), tags='led_grid')
            
    def toggle_grid(self):
        """Toggle grid visibility"""
        self.canvas.delete('led_grid')
        if self.grid_visible.get():
            self.draw_led_grid()
            
    def update_grid(self):
        """Update grid when array size changes"""
        if self.grid_corners:
            self.calculate_led_positions()
            if self.grid_visible.get():
                self.canvas.delete('led_grid')
                self.draw_led_grid()
                
    def auto_align(self):
        """Automatic alignment using image processing"""
        if self.original_image is None:
            messagebox.showwarning("Warning", "Please load an image first")
            return
            
        try:
            # Convert to grayscale for processing
            gray = cv2.cvtColor(self.original_image, cv2.COLOR_RGB2GRAY)
            
            # Apply Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Threshold to find bright spots (LEDs)
            _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Filter contours by area and aspect ratio
            led_candidates = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > 10:  # Minimum area threshold
                    x, y, w, h = cv2.boundingRect(contour)
                    aspect_ratio = w / h
                    if 0.5 < aspect_ratio < 2.0:  # Roughly square
                        center = (x + w//2, y + h//2)
                        led_candidates.append(center)
            
            if len(led_candidates) >= 4:
                # Try to arrange candidates in a grid
                self.auto_arrange_grid(led_candidates)
                self.status_var.set(f"Auto-alignment found {len(led_candidates)} LED candidates")
            else:
                messagebox.showinfo("Info", "Could not find enough LED candidates for auto-alignment")
                
        except Exception as e:
            messagebox.showerror("Error", f"Auto-alignment failed: {str(e)}")
            
    def auto_arrange_grid(self, candidates):
        """Arrange LED candidates into a grid"""
        # This is a simplified grid arrangement
        # In practice, you might want more sophisticated clustering
        n = self.array_size.get()
        expected_leds = n * n
        
        if len(candidates) < expected_leds:
            messagebox.showwarning("Warning", 
                                 f"Found {len(candidates)} candidates, expected {expected_leds}")
        
        # For now, just use the first n*n candidates
        self.led_positions = []
        for i, (x, y) in enumerate(candidates[:expected_leds]):
            row = i // n
            col = i % n
            # Scale coordinates to display coordinates
            display_x = int(x * self.scale_factor)
            display_y = int(y * self.scale_factor)
            self.led_positions.append((display_x, display_y, row, col))
            
        if self.grid_visible.get():
            self.canvas.delete('led_grid')
            self.draw_led_grid()
            
    def measure_brightness(self):
        """Measure brightness for each LED with enhanced methods for dark LEDs"""
        if self.original_image is None:
            messagebox.showwarning("Warning", "Please load an image first")
            return
            
        # Determine which positions to use based on detection method
        positions_to_use = []
        
        if self.measurement_method.get() == "manual" and self.manual_positions:
            # Use manual positions
            n = self.array_size.get()
            for row in range(n):
                for col in range(n):
                    if (row, col) in self.manual_positions:
                        x, y = self.manual_positions[(row, col)]
                        positions_to_use.append((x, y, row, col))
                        
        else:
            # Use grid-based positions
            if not self.led_positions:
                messagebox.showwarning("Warning", "Please define LED positions first (use grid corners or manual positioning)")
                return
            positions_to_use = self.led_positions
            
        # Clear previous results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
            
        # Prepare image for measurement
        work_image = self.original_image.copy()
        
        # Apply enhancements if requested
        if self.enhance_dark_leds.get():
            work_image = self.enhance_dark_regions(work_image)
            
        results = {}
        region_size = self.sampling_size.get()
        
        for display_x, display_y, row, col in positions_to_use:
            # Convert display coordinates back to original image coordinates
            orig_x = int(display_x / self.scale_factor)
            orig_y = int(display_y / self.scale_factor)
            
            # Define sampling region
            x1 = max(0, orig_x - region_size)
            y1 = max(0, orig_y - region_size)
            x2 = min(work_image.shape[1], orig_x + region_size + 1)
            y2 = min(work_image.shape[0], orig_y + region_size + 1)
            
            # Extract region
            region = work_image[y1:y2, x1:x2]
            
            if region.size > 0:
                # Calculate average RGB values
                avg_r = np.mean(region[:, :, 0])
                avg_g = np.mean(region[:, :, 1])
                avg_b = np.mean(region[:, :, 2])
                
                # Calculate brightness (luminance)
                brightness = 0.299 * avg_r + 0.587 * avg_g + 0.114 * avg_b
                
                results[(row, col)] = {
                    'brightness': brightness,
                    'r': avg_r,
                    'g': avg_g,
                    'b': avg_b,
                    'interpolated': False
                }
        
        # Apply interpolation for missing measurements if selected
        if self.measurement_method.get() == "interpolation":
            results = self.interpolate_grid_measurements(results)
            
        # Convert to list format and display results
        measurement_list = []
        
        # Show in grid order
        n = self.array_size.get()
        led_id = 1;
        
        for row in range(n):
            for col in range(n):
                key = (row, col)
                if key in results:
                    data = results[key]
                    measurement_list.append({
                        'id': led_id,
                        'row': row,
                        'col': col,
                        'brightness': data['brightness'],
                        'r': data['r'],
                        'g': data['g'],
                        'b': data['b'],
                        'interpolated': data.get('interpolated', False)
                    })
                    
                    # Add to results tree with indicator for interpolated values
                    brightness_text = f"{data['brightness']:.1f}"
                    if data.get('interpolated', False):
                        brightness_text += "*"  # Mark interpolated values
                        
                    self.results_tree.insert('', 'end', values=(
                        led_id, row, col, brightness_text, 
                        f"{data['r']:.1f}", f"{data['g']:.1f}", f"{data['b']:.1f}"
                    ))
                    
                    led_id += 1
        
        self.measurement_results = measurement_list;
        
        # Update status with method used
        method_name = {
            'direct': 'Direct Detection',
            'interpolation': 'Grid Interpolation', 
            'manual': 'Manual Positioning'
        }[self.measurement_method.get()]
        
        interpolated_count = sum(1 for r in measurement_list if r.get('interpolated', False))
        status_msg = f"Measured {len(measurement_list)} LEDs using {method_name}"
        if interpolated_count > 0:
            status_msg += f" ({interpolated_count} interpolated*)"
            
        self.status_var.set(status_msg)
        
    def export_csv(self):
        """Export results to CSV file"""
        if not hasattr(self, 'measurement_results') or not self.measurement_results:
            messagebox.showwarning("Warning", "No measurement results to export")
            return
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'w', newline='') as csvfile:
                    fieldnames = ['led_id', 'row', 'col', 'brightness', 'r', 'g', 'b', 'interpolated', 'detection_method', 'measurement_method']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    
                    writer.writeheader()
                    for result in self.measurement_results:
                        result_copy = result.copy()
                        result_copy['detection_method'] = self.detection_method.get()
                        result_copy['measurement_method'] = self.measurement_method.get()
                        if 'interpolated' not in result_copy:
                            result_copy['interpolated'] = False
                        if 'id' in result_copy:
                            result_copy['led_id'] = result_copy['id']
                            del result_copy['id']
                        else:
                            result_copy['led_id'] = result_copy.get('row', 0) * 10 + result_copy.get('col', 0) + 1
                        writer.writerow(result_copy)
                        
                messagebox.showinfo("Success", f"Results exported to {file_path}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export results: {str(e)}")
                
    def save_results(self):
        """Save all results and configuration"""
        if not hasattr(self, 'measurement_results'):
            messagebox.showwarning("Warning", "No results to save")
            return
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                data = {
                    'array_size': self.array_size.get(),
                    'grid_corners': self.grid_corners,
                    'led_positions': [(x, y, int(row), int(col)) for x, y, row, col in self.led_positions],
                    'measurement_results': self.measurement_results
                }
                
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                    
                messagebox.showinfo("Success", f"Results saved to {file_path}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save results: {str(e)}")
                
    def start_manual_positioning(self):
        """Start manual positioning mode for dark LEDs"""
        self.manual_positioning = True
        self.status_var.set("Manual positioning mode. Click on LED positions in order (row by row, left to right)")
        messagebox.showinfo("Manual Positioning", 
                          f"Click on each LED position in order:\n"
                          f"Start from top-left, go left to right, then next row.\n"
                          f"For a {self.array_size.get()}×{self.array_size.get()} grid, click {self.array_size.get()**2} positions.\n"
                          f"Right-click when done or press ESC to cancel.")
        
        # Bind right-click to finish manual positioning
        self.canvas.bind("<Button-2>", self.finish_manual_positioning)  # Right-click on Mac
        self.canvas.bind("<Button-3>", self.finish_manual_positioning)  # Right-click on other systems
        self.root.bind("<Escape>", self.cancel_manual_positioning)
        
    def handle_manual_positioning(self, x, y):
        """Handle manual LED positioning clicks"""
        n = self.array_size.get()
        current_count = len(self.manual_positions)
        
        if current_count >= n * n:
            messagebox.showwarning("Complete", "All LED positions have been set!")
            self.finish_manual_positioning(None)
            return
            
        # Calculate row and column
        row = current_count // n
        col = current_count % n
        
        # Store position
        self.manual_positions[(row, col)] = (x, y)
        
        # Draw marker
        self.canvas.create_oval(x-4, y-4, x+4, y+4, fill='orange', outline='red', 
                              width=2, tags='manual_led')
        self.canvas.create_text(x+10, y-10, text=f'{row},{col}', fill='red', 
                              font=('Arial', 9), tags='manual_led')
        
        self.status_var.set(f"Manual positioning: {current_count + 1}/{n*n} LEDs positioned")
        
    def finish_manual_positioning(self, event):
        """Finish manual positioning mode"""
        self.manual_positioning = False
        n = self.array_size.get()
        
        if len(self.manual_positions) == n * n:
            # Convert manual positions to led_positions format
            self.led_positions = []
            for row in range(n):
                for col in range(n):
                    if (row, col) in self.manual_positions:
                        x, y = self.manual_positions[(row, col)]
                        self.led_positions.append((x, y, row, col))
            
            self.status_var.set(f"Manual positioning complete: {len(self.led_positions)} LEDs positioned")
            if self.grid_visible.get():
                self.canvas.delete('led_grid')
                self.draw_led_grid()
        else:
            self.status_var.set(f"Manual positioning incomplete: {len(self.manual_positions)}/{n*n} LEDs")
            
        # Unbind events
        self.canvas.unbind("<Button-2>")
        self.canvas.unbind("<Button-3>")
        self.root.unbind("<Escape>")
        
    def cancel_manual_positioning(self, event):
        """Cancel manual positioning mode"""
        self.manual_positioning = False
        self.manual_positions.clear()
        self.canvas.delete('manual_led')
        self.status_var.set("Manual positioning cancelled")
        
        # Unbind events
        self.canvas.unbind("<Button-2>")
        self.canvas.unbind("<Button-3>")
        self.root.unbind("<Escape>")
        
    def start_pixel_adjustment(self):
        """Start pixel adjustment mode to fine-tune LED positions"""
        if not self.led_positions:
            messagebox.showwarning("Warning", "Please define grid corners first")
            return
            
        self.adjusting_pixels = True
        self.selected_led_index = None
        self.status_var.set("Pixel adjustment mode: Click near any LED to select and move it. ESC to exit.")
        
        # Bind escape key to exit adjustment mode
        self.root.bind('<Escape>', self.exit_pixel_adjustment)
        self.root.focus_set()
        
        # Highlight LED positions for easier selection
        self.draw_led_grid_highlighted()
        
    def handle_pixel_adjustment(self, x, y):
        """Handle pixel adjustment clicks"""
        if self.selected_led_index is None:
            # First click - select the nearest LED
            led_index = self.find_nearest_led(x, y)
            if led_index is not None:
                self.selected_led_index = led_index
                self.draw_led_grid_highlighted()
                old_x, old_y, row, col = self.led_positions[led_index]
                self.status_var.set(f"Selected LED ({row},{col}). Click new position to move it.")
        else:
            # Second click - move the selected LED to new position
            old_x, old_y, row, col = self.led_positions[self.selected_led_index]
            self.led_positions[self.selected_led_index] = (x, y, row, col)
            self.selected_led_index = None
            self.draw_led_grid_highlighted()
            self.status_var.set(f"Moved LED ({row},{col}) to new position")
            
    def find_nearest_led(self, x, y, threshold=15):
        """Find the nearest LED position within threshold distance"""
        if not self.led_positions:
            return None
            
        min_distance = float('inf')
        nearest_index = None
        
        for i, (led_x, led_y, row, col) in enumerate(self.led_positions):
            distance = np.sqrt((x - led_x)**2 + (y - led_y)**2)
            if distance < threshold and distance < min_distance:
                min_distance = distance
                nearest_index = i
                
        return nearest_index
        
    def draw_led_grid_highlighted(self):
        """Draw LED grid with highlighting for adjustment mode"""
        self.canvas.delete('led_grid')
        if not self.led_positions:
            return
            
        for i, (x, y, row, col) in enumerate(self.led_positions):
            if i == self.selected_led_index:
                # Highlight selected LED
                self.canvas.create_oval(x-5, y-5, x+5, y+5, fill='red', outline='darkred', 
                                      width=3, tags='led_grid')
                self.canvas.create_text(x+10, y-10, text=f'{row},{col}', fill='red', 
                                      font=('Arial', 10, 'bold'), tags='led_grid')
            else:
                # Normal LED markers but more prominent for selection
                self.canvas.create_oval(x-4, y-4, x+4, y+4, fill='yellow', outline='orange', 
                                      width=2, tags='led_grid')
                self.canvas.create_text(x+8, y-8, text=f'{row},{col}', fill='orange', 
                                      font=('Arial', 8), tags='led_grid')
                
    def exit_pixel_adjustment(self, event=None):
        """Exit pixel adjustment mode"""
        self.adjusting_pixels = False
        self.selected_led_index = None
        self.status_var.set("Pixel adjustment mode disabled")
        self.root.unbind('<Escape>')
        
        # Redraw normal grid
        if self.grid_visible.get():
            self.draw_led_grid()

    def enhance_dark_regions(self, image):
        """Enhance dark regions in the image for better LED detection"""
        # Convert to float for processing
        enhanced = image.astype(np.float32)
        
        # Apply gamma correction to brighten dark areas
        gamma = 0.5  # Values < 1 brighten the image
        enhanced = 255.0 * np.power(enhanced / 255.0, gamma)
        
        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        lab = cv2.cvtColor(enhanced.astype(np.uint8), cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)
        
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        l = clahe.apply(l)
        
        enhanced = cv2.merge([l, a, b])
        enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2RGB)
        
        return enhanced
        

        
    def interpolate_grid_measurements(self, measurements):
        """Interpolate measurements for missing or dark LEDs"""
        n = self.array_size.get()
        interpolated = measurements.copy()
        
        for row in range(n):
            for col in range(n):
                key = (row, col)
                if key not in measurements or measurements[key]['brightness'] < 10:  # Dark threshold
                    # Find nearby measurements for interpolation
                    nearby_values = []
                    
                    # Check 8 surrounding positions
                    for dr in [-1, 0, 1]:
                        for dc in [-1, 0, 1]:
                            if dr == 0 and dc == 0:
                                continue
                            nr, nc = row + dr, col + dc
                            nearby_key = (nr, nc)
                            if (0 <= nr < n and 0 <= nc < n and 
                                nearby_key in measurements and 
                                measurements[nearby_key]['brightness'] >= 10):
                                nearby_values.append(measurements[nearby_key])
                    
                    if nearby_values:
                        # Interpolate values
                        avg_brightness = np.mean([v['brightness'] for v in nearby_values])
                        avg_r = np.mean([v['r'] for v in nearby_values])
                        avg_g = np.mean([v['g'] for v in nearby_values])
                        avg_b = np.mean([v['b'] for v in nearby_values])
                        
                        interpolated[key] = {
                            'brightness': avg_brightness * 0.1,  # Assume dark LED is 10% of neighbors
                            'r': avg_r * 0.1,
                            'g': avg_g * 0.1,
                            'b': avg_b * 0.1,
                            'interpolated': True
                        }
                    else:
                        # No nearby measurements, use minimum values
                        interpolated[key] = {
                            'brightness': 1.0,
                            'r': 1.0,
                            'g': 1.0,
                            'b': 1.0,
                            'interpolated': True
                        }
                        
        return interpolated


        

            

            

        

                                  
    def clear_all_detections(self):
        """Clear all detection results"""
        self.save_state()  # Save state before clearing
        self.grid_corners = []
        self.led_positions = []
        self.manual_positions = {}
        
        # Exit corner editing mode if active
        if hasattr(self, 'editing_corners') and self.editing_corners:
            self.exit_corner_editing()
        
        # Clear canvas overlays
        self.canvas.delete('corners')
        self.canvas.delete('led_grid')
        self.canvas.delete('manual_led')
        
        self.status_var.set("All detections cleared")
        
    def edit_grid_corners(self):
        """Enable corner editing mode"""
        if len(self.grid_corners) != 4:
            messagebox.showwarning("Warning", "Please define grid corners first")
            return
            
        self.editing_corners = True
        self.draw_grid_corners()  # Redraw with editing colors
        self.status_var.set("Corner editing mode: Click near any corner to move it. Press ESC to exit.")
        
        # Bind escape key to exit editing mode
        self.root.bind('<Escape>', self.exit_corner_editing)
        self.root.focus_set()
        
    def find_nearest_corner(self, x, y, threshold=20):
        """Find the nearest corner within threshold distance"""
        if not self.grid_corners:
            return None
            
        min_distance = float('inf')
        nearest_index = None
        
        for i, (cx, cy) in enumerate(self.grid_corners):
            distance = np.sqrt((x - cx)**2 + (y - cy)**2)
            if distance < threshold and distance < min_distance:
                min_distance = distance
                nearest_index = i
                
        return nearest_index
        
    def exit_corner_editing(self, event=None):
        """Exit corner editing mode"""
        if hasattr(self, 'editing_corners'):
            self.editing_corners = False
            self.draw_grid_corners()  # Redraw with normal colors
            self.status_var.set("Corner editing mode disabled")
            self.root.unbind('<Escape>')
            
    # Undo/Redo System
    def save_state(self):
        """Save current state for undo functionality"""
        state = {
            'grid_corners': self.grid_corners.copy(),
            'led_positions': self.led_positions.copy(),
            'manual_positions': self.manual_positions.copy(),
            'array_size': self.array_size.get()
        }
        
        # Add to history
        self.history.append(state)
        
        # Limit history size
        if len(self.history) > self.max_history:
            self.history.pop(0)
            
        # Clear redo stack when new action is performed
        self.redo_stack.clear()
        
    def undo(self, event=None):
        """Undo last action"""
        if not self.history:
            self.status_var.set("Nothing to undo")
            return
            
        # Save current state to redo stack
        current_state = {
            'grid_corners': self.grid_corners.copy(),
            'led_positions': self.led_positions.copy(),
            'manual_positions': self.manual_positions.copy(),
            'array_size': self.array_size.get()
        }
        self.redo_stack.append(current_state)
        
        # Restore previous state
        previous_state = self.history.pop()
        self.grid_corners = previous_state['grid_corners']
        self.led_positions = previous_state['led_positions']
        self.manual_positions = previous_state['manual_positions']
        self.array_size.set(previous_state['array_size'])
        
        # Redraw everything
        self.draw_grid_corners()
        if self.grid_visible.get():
            self.draw_led_grid()
            
        self.status_var.set("Undo completed")
        
    def redo(self, event=None):
        """Redo last undone action"""
        if not self.redo_stack:
            self.status_var.set("Nothing to redo")
            return
            
        # Save current state to history
        current_state = {
            'grid_corners': self.grid_corners.copy(),
            'led_positions': self.led_positions.copy(),
            'manual_positions': self.manual_positions.copy(),
            'array_size': self.array_size.get()
        }
        self.history.append(current_state)
        
        # Restore redo state
        redo_state = self.redo_stack.pop()
        self.grid_corners = redo_state['grid_corners']
        self.led_positions = redo_state['led_positions']
        self.manual_positions = redo_state['manual_positions']
        self.array_size.set(redo_state['array_size'])
        
        # Redraw everything
        self.draw_grid_corners()
        if self.grid_visible.get():
            self.draw_led_grid()
            
        self.status_var.set("Redo completed")
        
    # Zoom System
    def on_mousewheel(self, event):
        """Handle mouse wheel for zoom"""
        # Determine zoom direction
        if event.delta > 0 or event.num == 4:  # Zoom in
            self.zoom_in()
        elif event.delta < 0 or event.num == 5:  # Zoom out
            self.zoom_out()
            
    def zoom_in(self):
        """Zoom in on the image"""
        if self.zoom_level < self.max_zoom:
            self.zoom_level += self.zoom_step
            self.apply_zoom()
            
    def zoom_out(self):
        """Zoom out on the image"""
        if self.zoom_level > self.min_zoom:
            self.zoom_level -= self.zoom_step
            self.apply_zoom()
            
    def reset_zoom(self):
        """Reset zoom to 100%"""
        self.zoom_level = 1.0
        self.apply_zoom()
        
    def apply_zoom(self):
        """Apply current zoom level to the displayed image"""
        if self.original_image is None:
            return
            
        # Update zoom label
        self.zoom_label.config(text=f"Zoom: {int(self.zoom_level * 100)}%")
        
        # Calculate new dimensions
        original_height, original_width = self.original_image.shape[:2]
        
        # Apply zoom to the image
        new_width = int(original_width * self.zoom_level)
        new_height = int(original_height * self.zoom_level)
        
        # Resize image
        zoomed_image = cv2.resize(self.original_image, (new_width, new_height), 
                                 interpolation=cv2.INTER_LINEAR)
        
        # Update scale factor for coordinate conversion
        self.scale_factor = min(self.canvas_width / new_width, 
                               self.canvas_height / new_height) * self.zoom_level
        
        # Convert to display format
        if len(zoomed_image.shape) == 3:
            display_image = Image.fromarray(zoomed_image)
        else:
            display_image = Image.fromarray(cv2.cvtColor(zoomed_image, cv2.COLOR_BGR2RGB))
            
        # Create PhotoImage
        self.photo = ImageTk.PhotoImage(display_image)
        
        # Update canvas
        self.canvas.delete("all")
        self.canvas.create_image(self.canvas_width//2, self.canvas_height//2, 
                               image=self.photo, anchor=tk.CENTER)
        
        # Redraw overlays with updated coordinates
        self.draw_grid_corners()
        if self.grid_visible.get():
            self.draw_led_grid()

def main():
    """Main function to run the PixelQ application"""
    try:
        # Create the main window
        root = tk.Tk()
        
        # Create the application instance
        app = PixelQApp(root)
        
        # Start the main event loop
        root.mainloop()
        
    except Exception as e:
        print(f"Error starting PixelQ application: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
