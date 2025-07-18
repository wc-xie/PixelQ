# PixelQ - LED Array Brightness Measurement Tool

A GUI application for measuring brightness of individual LEDs in an array from camera images with advanced detection methods for complex LED patterns.

## Features

- **Image Loading**: Load color camera images of LED arrays
- **Multiple Detection Methods**:
  - **Grid-based**: Traditional rectangular grid alignment  
  - **Boundary Region**: Define irregular regions with quadrilateral boundaries
- **Interactive Alignment**: Define grid corners for precise alignment
- **Advanced Measurement Options**:
  - Direct detection for bright LEDs
  - Grid interpolation for dark/missing LEDs  
  - Manual positioning for precise control
  - Dark LED enhancement with gamma correction and CLAHE
  - Adjustable sampling area size
- **Data Export**: Export results to CSV format with detection method information
- **Save/Load**: Save measurement sessions for later analysis

## Detection Methods

### 1. **Boundary Region Detection**
- Draw a quadrilateral boundary around the LED region
- Perfect for isolating specific LED sections
- Good for irregular LED arrangements

### 2. **Grid-based Detection (Traditional)**
- Define rectangular grid corners for regular arrays
- Good for perfectly aligned rectangular LED arrays
- Uses bilinear interpolation for positioning

## Handling Dark LEDs

The application provides several methods to handle dark or dim LEDs that are difficult to detect:

### 1. **Manual Positioning Mode**
- Click "Manual Position Mode" to manually click on each LED location
- Click LEDs in order: left to right, top to bottom
- Right-click when done or press ESC to cancel
- Most accurate for dark LEDs

### 2. **Grid Interpolation**
- Select "Grid Interpolation" measurement method
- Automatically estimates brightness of dark LEDs based on nearby bright LEDs
- Interpolated values are marked with "*" in results

### 3. **Dark LED Enhancement**
- Enable "Enhance dark LEDs" to apply gamma correction and adaptive histogram equalization
- Brightens dark regions while preserving bright areas
- Helps manual positioning of dim LEDs

### 4. **Adjustable Sampling Area**
- Increase sampling area size (3-15 pixels) for better averaging
- Larger areas reduce noise but may include neighboring LEDs
- Smaller areas are more precise but more sensitive to positioning

## Installation

1. Make sure you have Python 3.7+ installed
2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. **Run the application**:
   ```bash
   python PixelQ.py
   ```

2. **Load an image**: Click "Load Image" to select your LED array photo

3. **Configure array size**: Set the n×n grid size in the "LED Array Configuration" panel

4. **Align the image** (choose one method):

   **Method 1: Manual Grid Definition**
   - Click "Define Grid Corners"
   - Click on the 4 corners of your LED array (top-left, top-right, bottom-right, bottom-left)
   - The software will calculate LED positions automatically

   **Method 2: Constraint Lines + Auto Align**
   - Click "Draw Constraint Line" and draw lines to help with alignment
   - Click "Auto Align" to automatically detect LED positions
   - Adjust as needed

   **Method 3: Complex LED Pattern Workflow (Your Image)**
   - Select "FFT Detection" method
   - Optionally draw boundary region if you want to focus on specific areas
   - Click "FFT Auto-Detect LEDs" 
   - Review detected positions (shown as yellow markers)
   - Click "Measure Brightness" to analyze all detected LEDs

   **Method 4: Boundary Region Workflow**
   - Select "Boundary Region" method
   - Click "Draw Boundary Region"
   - Click 4 points to define quadrilateral boundary
   - Click "FFT Auto-Detect LEDs" to find LEDs within boundary
   - Proceed with measurement

5. **Measure brightness**: Click "Measure Brightness" to analyze each LED

6. **Export results**: Use "Export to CSV" to save measurements

## Controls

### File Operations
- **Load Image**: Open a camera image file
- **Load Background**: Load background image for subtraction
- **Save Results**: Save complete session data (JSON format)

### LED Array Configuration
- **Array Size**: Set grid dimensions (n×n) - used for grid-based detection
- **Show Grid**: Toggle grid overlay visibility

### Detection & Alignment
- **Detection Method**: Choose between Grid-based, FFT Detection, or Boundary Region
- **Draw Constraint Line**: Draw reference lines for alignment (grid method)
- **Clear Constraint Lines**: Remove all constraint lines
- **Define Grid Corners**: Manually set the 4 corners of LED array (grid method)
- **Draw Boundary Region**: Define quadrilateral region for LED detection
- **FFT Auto-Detect LEDs**: Automatically find all LEDs using advanced algorithms
- **Clear All Detections**: Remove all detection results and boundaries

### Measurement
- **Measurement Method**: Choose detection approach (Direct/Interpolation/Manual)
- **Sampling Area**: Adjust pixel area sampled around each LED
- **Enhance Dark LEDs**: Apply image enhancement for better detection
- **Background Subtraction**: Use background image to highlight LEDs
- **Measure Brightness**: Calculate brightness for each detected LED
- **Manual Position Mode**: Manually click on each LED location for dark LEDs
- **Export to CSV**: Save results in spreadsheet format

## Measurement Methods

Choose from three measurement approaches in the "Measurement" panel:

1. **Direct Detection**: Standard measurement using calculated grid positions
2. **Grid Interpolation**: Estimates dark LED values from neighboring bright LEDs  
3. **Manual Positioning**: Click on each LED location manually for maximum accuracy

## Advanced Options

- **Sampling Area**: Adjust the pixel area sampled around each LED (3-15 pixels)
- **Enhance Dark LEDs**: Apply image enhancement to better detect dim LEDs
- **Background Subtraction**: Use a background image to highlight LED differences

## Output Format

The CSV export includes:
- `row`: LED row position (0-indexed)
- `col`: LED column position (0-indexed) 
- `brightness`: Calculated brightness value (0-255)
- `r`: Average red channel value (0-255)
- `g`: Average green channel value (0-255)
- `b`: Average blue channel value (0-255)
- `interpolated`: True if value was estimated from neighbors (for dark LEDs)
- `method`: Measurement method used (direct/interpolation/manual)

## Tips for Best Results

1. **Image Quality**: Use well-lit, high-resolution images with minimal camera distortion
2. **Alignment**: Take time to accurately define grid corners or constraint lines
3. **LED Spacing**: Ensure LEDs are clearly separated and visible
4. **Background**: Use contrasting backgrounds to help with automatic detection
5. **Multiple Measurements**: Take several photos and average results for better accuracy
6. **Dark LEDs**: 
   - Use manual positioning for most accurate results
   - Try background subtraction with LEDs-off image
   - Enable dark LED enhancement for better auto-detection
   - Consider interpolation for partially visible LEDs

## Troubleshooting

- **"Could not find enough LED candidates"**: Try adjusting lighting or using manual grid definition
- **Misaligned grid**: Redefine grid corners more precisely
- **Missing LEDs**: Check that all LEDs are lit and visible in the image
- **Poor brightness readings**: Ensure LEDs are not oversaturated or too dim

## Technical Details

- Brightness calculation uses standard luminance formula: 0.299×R + 0.587×G + 0.114×B
- Sampling area around each LED center is 11×11 pixels (adjustable in code)
- Automatic detection uses Otsu thresholding and contour analysis
- Grid interpolation uses bilinear interpolation between corner points
