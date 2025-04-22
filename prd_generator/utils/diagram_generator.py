"""
Diagram Generator module for creating Mermaid diagrams using an external microservice
"""
import os
import subprocess
import tempfile
import base64
import json
import requests
from pathlib import Path
import random
from PIL import Image, ImageDraw, ImageFont
import textwrap
import io
import re
from typing import Tuple


class DiagramGenerator:
    """Generator for creating diagrams from Mermaid syntax using a microservice."""
    
    def __init__(self, config=None):
        """Initialize the diagram generator."""
        # Define common diagram types for better recognition
        self.diagram_types = {
            "sequenceDiagram": "Sequence Diagram",
            "flowchart": "Flowchart",
            "graph": "Flowchart",
            "classDiagram": "Class Diagram",
            "erDiagram": "ER Diagram",
            "gantt": "Gantt Chart",
            "pie": "Pie Chart",
            "stateDiagram": "State Diagram",
            "journey": "User Journey"
        }
        
        # Configure the microservice URL from config or use default
        self.config = config
        if config:
            self.microservice_url = config.mermaid_service_url
        else:
            self.microservice_url = "http://localhost:3000/convert/image"
        
        print(f"Mermaid service URL: {self.microservice_url}")
    
    def generate_diagram(self, mermaid_code: str, output_path: str) -> bool:
        """
        Generate a diagram from Mermaid syntax and save to file.
        
        Args:
            mermaid_code: The Mermaid syntax for the diagram
            output_path: Path to save the generated diagram
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Clean and normalize the mermaid code
        mermaid_code = self._clean_mermaid_code(mermaid_code)
        
        # Try generating diagram with the microservice
        if self._generate_using_microservice(mermaid_code, output_path):
            # Optimize the generated image
            self._optimize_image(output_path)
            return True
        
        # If microservice fails, try alternative methods
        methods = [
            self._generate_using_mermaid_cli,
            self._generate_using_kroki_api,
            self._generate_using_mermaid_api,
            self._create_diagram_placeholder  # Added as a reliable fallback
        ]
        
        # Determine diagram complexity to adjust image size
        complexity = self._estimate_diagram_complexity(mermaid_code)
        
        for method in methods:
            try:
                success = method(mermaid_code, output_path, complexity)
                if success:
                    # Optimize the generated image
                    self._optimize_image(output_path)
                    return True
            except Exception as e:
                print(f"Error generating diagram with method {method.__name__}: {e}")
        
        return False

    def _generate_using_microservice(self, mermaid_code: str, output_path: str) -> bool:
        """Generate diagram using the local microservice."""
        try:
            # Prepare request payload
            payload = {
                "mermaidSyntax": mermaid_code
            }
            
            # Send POST request to the microservice
            response = requests.post(self.microservice_url, json=payload, timeout=30)
            
            # Check if request was successful
            if response.status_code == 200:
                # Save the image to the output file
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                return os.path.exists(output_path) and os.path.getsize(output_path) > 0
            else:
                print(f"Error: Microservice returned status code {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"Error using diagram microservice: {e}")
            return False
    
    def _clean_mermaid_code(self, mermaid_code: str) -> str:
        """Clean and normalize mermaid code for better rendering."""
        code = mermaid_code.strip()
        
        # Ensure code has proper opening format
        for diagram_type in self.diagram_types.keys():
            if code.startswith(diagram_type):
                return code
                
        # For flowcharts, ensure they have the TD (top-down) direction if not specified
        if re.match(r'^flowchart\s*$', code.split('\n')[0]):
            code = code.replace('flowchart', 'flowchart TD')
        elif re.match(r'^graph\s*$', code.split('\n')[0]):
            code = code.replace('graph', 'graph TD')
            
        return code
    
    def _estimate_diagram_complexity(self, mermaid_code: str) -> dict:
        """Estimate diagram complexity to determine appropriate image dimensions."""
        lines = mermaid_code.count('\n') + 1
        nodes = len(re.findall(r'[\[\(\{].*?[\]\)\}]', mermaid_code))
        connections = len(re.findall(r'-->', mermaid_code)) + len(re.findall(r'-', mermaid_code))
        
        # Determine diagram type
        diagram_type = "generic"
        for key in self.diagram_types:
            if mermaid_code.startswith(key):
                diagram_type = key
                break
        
        # Calculate suggested dimensions based on complexity
        width = max(800, min(nodes * 100, 2000))
        
        if diagram_type == "sequenceDiagram":
            height = max(600, min(lines * 50, 2000))
            width = max(800, min(100 * mermaid_code.count("participant"), 2000))
        elif diagram_type in ["gantt", "journey"]:
            height = max(600, min(lines * 40, 2000))
        elif "flowchart" in diagram_type or "graph" in diagram_type:
            height = max(600, min((nodes + connections) * 70, 2000))
        else:
            height = max(600, min(lines * 30, 2000))
            
        return {
            "diagram_type": diagram_type,
            "nodes": nodes,
            "connections": connections,
            "lines": lines,
            "width": width,
            "height": height
        }
    
    def _generate_using_mermaid_cli(self, mermaid_code: str, output_path: str, complexity: dict = None) -> bool:
        """Generate diagram using Mermaid CLI if installed."""
        try:
            # Check if mmdc (Mermaid CLI) is installed
            subprocess.run(['mmdc', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Create temporary file for Mermaid code
            with tempfile.NamedTemporaryFile('w', suffix='.mmd', delete=False) as f:
                mermaid_file = f.name
                f.write(mermaid_code)
            
            # Set diagram dimensions
            width = str(complexity.get('width', 800)) if complexity else "800"
            height = str(complexity.get('height', 600)) if complexity else "600"
            
            # Generate diagram using Mermaid CLI with specified dimensions
            subprocess.run([
                'mmdc', 
                '-i', mermaid_file, 
                '-o', output_path,
                '-w', width,
                '-H', height,
                '--backgroundColor', '#ffffff'
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            
            # Clean up temporary file
            os.remove(mermaid_file)
            
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def _generate_using_kroki_api(self, mermaid_code: str, output_path: str, complexity: dict = None) -> bool:
        """Generate diagram using Kroki API which has better rendering capabilities."""
        try:
            # Prepare API request
            url = "https://kroki.io/mermaid/png"
            
            # Add dimensions to the request if available
            width = complexity.get('width', 800) if complexity else 800
            height = complexity.get('height', 600) if complexity else 600
            
            # Encode the payload as expected by Kroki API
            payload = json.dumps({
                "diagram": mermaid_code,
                "width": width,
                "height": height
            })
            encoded_payload = base64.urlsafe_b64encode(payload.encode('utf-8')).decode('utf-8')
            
            # Send the request
            response = requests.post(
                url, 
                data=encoded_payload,
                headers={'Content-Type': 'text/plain'},
                timeout=30
            )
            response.raise_for_status()
            
            # Save the image
            with open(output_path, 'wb') as f:
                f.write(response.content)
                
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except Exception as e:
            print(f"Error using Kroki API: {e}")
            return False
    
    def _generate_using_mermaid_api(self, mermaid_code: str, output_path: str, complexity: dict = None) -> bool:
        """Generate diagram using Mermaid online service."""
        try:
            # Encode the Mermaid code
            encoded = base64.b64encode(mermaid_code.encode('utf-8')).decode('utf-8')
            
            # Use Mermaid.ink service to get the image
            # Add parameters for sizing
            width = complexity.get('width', 800) if complexity else 800
            height = complexity.get('height', 600) if complexity else 600
            
            url = f"https://mermaid.ink/img/{encoded}?width={width}&height={height}"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # Save the image
            with open(output_path, 'wb') as f:
                f.write(response.content)
                
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except Exception:
            return False
            
    def _create_diagram_placeholder(self, mermaid_code: str, output_path: str, complexity: dict = None) -> bool:
        """Create a smart placeholder image with the diagram code that simulates the actual diagram."""
        try:
            # Use complexity info or default values
            width = complexity.get('width', 900) if complexity else 900
            height = complexity.get('height', 700) if complexity else 700
            
            # Extract diagram type from mermaid code
            diagram_type = "diagram"
            for key, value in self.diagram_types.items():
                if mermaid_code.strip().startswith(key):
                    diagram_type = value
                    break
            
            # Create a blank image with a colored background
            background_color = (248, 250, 252)  # Very light blue-gray
            text_color = (60, 60, 80)  # Dark blue-gray
            border_color = (100, 120, 200)  # Medium blue-purple
            
            # Create image and drawing context
            img = Image.new('RGB', (width, height), background_color)
            draw = ImageDraw.Draw(img)
            
            # Draw border
            border_width = 3
            draw.rectangle([0, 0, width-1, height-1], outline=border_color, width=border_width)
            
            # Try to load a font, fall back to default if not available
            try:
                font_path = None
                # Check for common font locations
                font_locations = [
                    "C:/Windows/Fonts/consola.ttf",  # Console font for code
                    "C:/Windows/Fonts/arial.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                    "/System/Library/Fonts/Menlo.ttc"
                ]
                for path in font_locations:
                    if os.path.exists(path):
                        font_path = path
                        break
                
                if font_path:
                    title_font = ImageFont.truetype(font_path, 32)
                    subtitle_font = ImageFont.truetype(font_path, 20)
                    code_font = ImageFont.truetype(font_path, 14)
                else:
                    title_font = ImageFont.load_default()
                    subtitle_font = title_font
                    code_font = ImageFont.load_default()
            except Exception:
                title_font = ImageFont.load_default()
                subtitle_font = title_font
                code_font = ImageFont.load_default()
            
            # Draw title
            title = f"{diagram_type}"
            draw.text((width//2, 30), title, fill=text_color, font=title_font, anchor="mt")
            
            # Draw note about mermaid code
            note = "Diagram based on the following Mermaid code:"
            draw.text((width//2, 80), note, fill=text_color, font=subtitle_font, anchor="mt")
            
            # Parse and visualize diagram structure
            self._visualize_diagram_structure(draw, mermaid_code, diagram_type, width, height, code_font, text_color, border_color)
            
            # Save the image
            img.save(output_path, format="PNG", optimize=True)
            
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except Exception as e:
            print(f"Error creating diagram placeholder: {e}")
            return False
    
    def _visualize_diagram_structure(self, draw, mermaid_code, diagram_type, width, height, code_font, text_color, border_color):
        """Visualize the structure of the diagram based on its type and content."""
        arrow_color = border_color
        
        # Draw code preview in a scrollable area (first few lines)
        code_preview = mermaid_code.split('\n')[:7]  # First 7 lines
        y_position = 120
        
        for line in code_preview:
            # Truncate very long lines
            if len(line) > 80:
                line = line[:77] + "..."
            draw.text((50, y_position), line, fill=text_color, font=code_font)
            y_position += 20
        
        # Add ellipsis if there are more lines
        if len(mermaid_code.split('\n')) > 7:
            draw.text((50, y_position), "...", fill=text_color, font=code_font)
            y_position += 30
        else:
            y_position += 10
        
        # Draw a line separator
        draw.line([50, y_position, width-50, y_position], fill=arrow_color, width=1)
        y_position += 20
        
        # Determine what to draw based on diagram type
        visual_y_start = y_position + 30
        visual_area_height = height - visual_y_start - 50
        
        if "sequence" in diagram_type.lower():
            self._draw_sequence_diagram(draw, mermaid_code, width, visual_y_start, visual_area_height, arrow_color)
        elif "class" in diagram_type.lower():
            self._draw_class_diagram(draw, mermaid_code, width, visual_y_start, visual_area_height, arrow_color)
        elif "flowchart" in diagram_type.lower() or "graph" in diagram_type.lower():
            self._draw_flowchart(draw, mermaid_code, width, visual_y_start, visual_area_height, arrow_color)
        elif "gantt" in diagram_type.lower():
            self._draw_gantt_chart(draw, mermaid_code, width, visual_y_start, visual_area_height, arrow_color, text_color, code_font)
        elif "er" in diagram_type.lower():
            self._draw_er_diagram(draw, mermaid_code, width, visual_y_start, visual_area_height, arrow_color)
        else:
            # Generic diagram visualization
            self._draw_generic_diagram(draw, mermaid_code, width, visual_y_start, visual_area_height, arrow_color)
    
    def _draw_sequence_diagram(self, draw, mermaid_code, width, y_start, height, arrow_color):
        """Draw a simplified sequence diagram visualization."""
        # Extract participants
        participants = re.findall(r'participant\s+([A-Za-z0-9_]+)', mermaid_code)
        if not participants:
            participants = re.findall(r'([A-Za-z0-9_]+)(?:\s*->>|\s*-->|\s*-[>x])', mermaid_code)
            participants = list(set(participants))[:5]  # Limit to first 5 unique participants
        
        if not participants:
            participants = ["Participant1", "Participant2", "Participant3"]  # Default
        
        # Calculate positions
        num_participants = min(len(participants), 5)  # Limit to 5 participants
        spacing = (width - 100) / (num_participants + 1)
        
        # Draw participants and lifelines
        participant_positions = {}
        for i, participant in enumerate(participants[:num_participants]):
            x = 50 + spacing * (i + 1)
            participant_positions[participant] = x
            
            # Draw actor
            draw.ellipse([x-25, y_start, x+25, y_start+50], outline=arrow_color, width=2)
            draw.line([x, y_start+50, x, y_start+height-50], fill=arrow_color, width=2)
            
            # Draw label
            label = participant[:10] + "..." if len(participant) > 10 else participant
            draw.text((x, y_start+25), label, fill=arrow_color, anchor="mm")
        
        # Draw some example arrows between participants
        arrow_y = y_start + 100
        arrow_spacing = min(80, (height - 150) / 3)
        
        # Draw at most 3 arrows
        for i in range(min(3, len(participant_positions))):
            if i + 1 < len(participant_positions):
                keys = list(participant_positions.keys())
                from_x = participant_positions[keys[i]]
                to_x = participant_positions[keys[i+1]]
                
                # Draw arrow
                draw.line([from_x, arrow_y, to_x, arrow_y], fill=arrow_color, width=2)
                draw.polygon([to_x-10, arrow_y-5, to_x, arrow_y, to_x-10, arrow_y+5], fill=arrow_color)
                
                # Draw return arrow in next row if space allows
                if i * 2 + 1 < 3:  # Ensure we don't exceed our arrow limit
                    arrow_y += arrow_spacing
                    draw.line([to_x, arrow_y, from_x, arrow_y], fill=arrow_color, width=2)
                    draw.polygon([from_x+10, arrow_y-5, from_x, arrow_y, from_x+10, arrow_y+5], fill=arrow_color)
            
            arrow_y += arrow_spacing
    
    def _draw_class_diagram(self, draw, mermaid_code, width, y_start, height, arrow_color):
        """Draw a simplified class diagram visualization."""
        # Extract classes
        classes = re.findall(r'class\s+([A-Za-z0-9_]+)', mermaid_code)
        if not classes:
            classes = ["Class1", "Class2", "BaseClass"]
        
        # Determine layout based on number of classes
        num_classes = min(len(classes), 5)  # Limit to 5 classes
        
        # Determine if we have inheritance relationships
        has_inheritance = "<|--" in mermaid_code or "--|>" in mermaid_code
        
        if has_inheritance:
            # Draw inheritance diagram
            base_y = y_start + 70
            base_x = width // 2
            base_width = 150
            base_height = 90
            
            # Draw base class
            draw.rectangle([base_x-base_width//2, base_y, base_x+base_width//2, base_y+base_height], 
                           outline=arrow_color, width=2)
            
            # Draw compartments
            draw.line([base_x-base_width//2, base_y+30, base_x+base_width//2, base_y+30], fill=arrow_color, width=1)
            draw.line([base_x-base_width//2, base_y+60, base_x+base_width//2, base_y+60], fill=arrow_color, width=1)
            
            # Draw class name
            base_class = classes[0] if classes else "BaseClass"
            draw.text((base_x, base_y+15), base_class, fill=arrow_color, anchor="mm")
            
            # Draw derived classes
            derived_y = base_y + base_height + 70
            spacing = (width - 100) / (min(num_classes, 3) + 1)
            
            for i in range(min(num_classes-1, 3)):
                derived_x = 50 + spacing * (i + 1)
                
                # Draw derived class
                draw.rectangle([derived_x-base_width//2, derived_y, derived_x+base_width//2, derived_y+base_height], 
                               outline=arrow_color, width=2)
                
                # Draw compartments
                draw.line([derived_x-base_width//2, derived_y+30, derived_x+base_width//2, derived_y+30], fill=arrow_color, width=1)
                
                # Draw class name
                class_name = classes[i+1] if i+1 < len(classes) else f"Class{i+1}"
                draw.text((derived_x, derived_y+15), class_name, fill=arrow_color, anchor="mm")
                
                # Draw inheritance arrow
                draw.line([derived_x, derived_y, base_x, base_y+base_height], fill=arrow_color, width=2)
                # Draw arrowhead
                draw.polygon([base_x, base_y+base_height, base_x-8, base_y+base_height+12, base_x+8, base_y+base_height+12], 
                             outline=arrow_color, fill=(248, 250, 252))
        else:
            # Draw regular class diagram
            class_width = 150
            class_height = 100
            
            # Calculate positions
            if num_classes <= 3:
                # Horizontal layout
                spacing = (width - 100) / (num_classes + 1)
                for i in range(num_classes):
                    x = 50 + spacing * (i + 1)
                    y = y_start + height // 2 - class_height // 2
                    
                    # Draw class
                    draw.rectangle([x-class_width//2, y, x+class_width//2, y+class_height], 
                                   outline=arrow_color, width=2)
                    
                    # Draw compartments
                    draw.line([x-class_width//2, y+30, x+class_width//2, y+30], fill=arrow_color, width=1)
                    draw.line([x-class_width//2, y+60, x+class_width//2, y+60], fill=arrow_color, width=1)
                    
                    # Draw class name
                    class_name = classes[i] if i < len(classes) else f"Class{i+1}"
                    draw.text((x, y+15), class_name, fill=arrow_color, anchor="mm")
                    
                    # If this isn't the last class, draw a connection line
                    if i < num_classes - 1:
                        next_x = 50 + spacing * (i + 2)
                        draw.line([x+class_width//2, y+class_height//2, next_x-class_width//2, y+class_height//2], 
                                  fill=arrow_color, width=2)
            else:
                # Grid layout for more classes (2x2)
                rows, cols = 2, 2
                for row in range(rows):
                    for col in range(cols):
                        idx = row * cols + col
                        if idx >= num_classes:
                            continue
                            
                        x = width * (col + 1) // (cols + 1)
                        y = y_start + 50 + row * (height - 100) // rows
                        
                        # Draw class
                        draw.rectangle([x-class_width//2, y, x+class_width//2, y+class_height], 
                                       outline=arrow_color, width=2)
                        
                        # Draw compartments
                        draw.line([x-class_width//2, y+30, x+class_width//2, y+30], fill=arrow_color, width=1)
                        draw.line([x-class_width//2, y+60, x+class_width//2, y+60], fill=arrow_color, width=1)
                        
                        # Draw class name
                        class_name = classes[idx] if idx < len(classes) else f"Class{idx+1}"
                        draw.text((x, y+15), class_name, fill=arrow_color, anchor="mm")
    
    def _draw_flowchart(self, draw, mermaid_code, width, y_start, height, arrow_color):
        """Draw a simplified flowchart visualization."""
        # Extract nodes and connections
        nodes = re.findall(r'([A-Za-z0-9_]+)(?:\s*\[|\s*\(|\s*\{)', mermaid_code)
        if not nodes:
            # Create some default nodes if we couldn't extract any
            nodes = ["Start", "Process", "Decision", "End"]
        
        # Determine layout
        num_nodes = min(len(nodes), 6)  # Limit to 6 nodes
        
        # Check if we have a top-down (TD) or left-right (LR) direction
        direction = "TD"  # Default
        if re.search(r'(?:flowchart|graph)\s+LR', mermaid_code):
            direction = "LR"
        
        if direction == "TD":
            # Top-down layout
            spacing_y = height / (num_nodes + 1)
            node_width = 120
            node_height = 60
            
            for i in range(num_nodes):
                y = y_start + spacing_y * (i + 1)
                
                # For the decision node (middle one)
                if i == num_nodes // 2:
                    # Draw diamond
                    diamond_points = [
                        (width//2, y - node_height//2),
                        (width//2 + node_width//2, y),
                        (width//2, y + node_height//2),
                        (width//2 - node_width//2, y)
                    ]
                    draw.polygon(diamond_points, outline=arrow_color, fill=(248, 250, 252), width=2)
                    node_name = nodes[i] if i < len(nodes) else "Decision"
                    draw.text((width//2, y), node_name, fill=arrow_color, anchor="mm")
                    
                    # If not the last node, draw arrow to next node
                    if i < num_nodes - 1:
                        next_y = y_start + spacing_y * (i + 2)
                        draw.line([width//2, y + node_height//2, width//2, next_y - node_height//2], fill=arrow_color, width=2)
                        draw.polygon([width//2-5, next_y-node_height//2-5, width//2, next_y-node_height//2, width//2+5, next_y-node_height//2-5], fill=arrow_color)
                    
                    # If decision node, add a branch
                    branch_x = width//2 + 120
                    draw.line([width//2 + node_width//2, y, branch_x, y], fill=arrow_color, width=2)
                    draw.polygon([branch_x-5, y-5, branch_x, y, branch_x-5, y+5], fill=arrow_color)
                    
                    # Add a small process box at the branch end
                    draw.rectangle([branch_x+10, y-20, branch_x+100, y+20], outline=arrow_color, width=2)
                    draw.text((branch_x+55, y), "Branch", fill=arrow_color, anchor="mm")
                else:
                    # Draw rectangle
                    draw.rectangle([width//2-node_width//2, y-node_height//2, width//2+node_width//2, y+node_height//2], 
                                   outline=arrow_color, width=2)
                    node_name = nodes[i] if i < len(nodes) else f"Node{i+1}"
                    draw.text((width//2, y), node_name, fill=arrow_color, anchor="mm")
                    
                    # If not the last node, draw arrow to next node
                    if i < num_nodes - 1 and i != (num_nodes // 2 - 1):  # Skip connection to decision node
                        next_y = y_start + spacing_y * (i + 2)
                        draw.line([width//2, y + node_height//2, width//2, next_y - node_height//2], fill=arrow_color, width=2)
                        draw.polygon([width//2-5, next_y-node_height//2-5, width//2, next_y-node_height//2, width//2+5, next_y-node_height//2-5], fill=arrow_color)
        else:
            # Left-right layout
            spacing_x = (width - 100) / (num_nodes + 1)
            node_width = 100
            node_height = 60
            center_y = y_start + height // 2
            
            for i in range(num_nodes):
                x = 50 + spacing_x * (i + 1)
                
                if i == num_nodes // 2:
                    # Decision node (diamond)
                    diamond_points = [
                        (x, center_y - node_height//2),
                        (x + node_width//2, center_y),
                        (x, center_y + node_height//2),
                        (x - node_width//2, center_y)
                    ]
                    draw.polygon(diamond_points, outline=arrow_color, fill=(248, 250, 252), width=2)
                    node_name = nodes[i] if i < len(nodes) else "Decision"
                    draw.text((x, center_y), node_name, fill=arrow_color, anchor="mm")
                    
                    # Branch going down
                    branch_y = center_y + 80
                    draw.line([x, center_y + node_height//2, x, branch_y], fill=arrow_color, width=2)
                    draw.polygon([x-5, branch_y-5, x, branch_y, x+5, branch_y-5], fill=arrow_color)
                    
                    # Box at branch end
                    draw.rectangle([x-40, branch_y+10, x+40, branch_y+50], outline=arrow_color, width=2)
                    draw.text((x, branch_y+30), "Branch", fill=arrow_color, anchor="mm")
                else:
                    # Regular node (rectangle)
                    draw.rectangle([x-node_width//2, center_y-node_height//2, x+node_width//2, center_y+node_height//2], 
                                   outline=arrow_color, width=2)
                    node_name = nodes[i] if i < len(nodes) else f"Node{i+1}"
                    draw.text((x, center_y), node_name, fill=arrow_color, anchor="mm")
                
                # Connect nodes with arrows
                if i < num_nodes - 1:
                    next_x = 50 + spacing_x * (i + 2)
                    draw.line([x + node_width//2, center_y, next_x - node_width//2, center_y], fill=arrow_color, width=2)
                    draw.polygon([next_x - node_width//2 - 5, center_y-5, next_x - node_width//2, center_y, next_x - node_width//2 - 5, center_y+5], fill=arrow_color)
    
    def _draw_er_diagram(self, draw, mermaid_code, width, y_start, height, arrow_color):
        """Draw a simplified ER diagram visualization."""
        # Extract entities
        entities = re.findall(r'([A-Za-z0-9_]+)\s*{', mermaid_code)
        if not entities:
            entities = ["Entity1", "Entity2", "Entity3"]
        
        # Limit to 3 entities
        num_entities = min(len(entities), 3)
        
        # Entity dimensions
        entity_width = 150
        entity_height = 120
        
        # Calculate positions
        spacing = (width - 100) / (num_entities + 1)
        
        for i in range(num_entities):
            x = 50 + spacing * (i + 1)
            y = y_start + height // 2 - entity_height // 2
            
            # Draw entity
            draw.rectangle([x-entity_width//2, y, x+entity_width//2, y+entity_height], outline=arrow_color, width=2)
            
            # Draw entity name at top
            entity_name = entities[i] if i < len(entities) else f"Entity{i+1}"
            draw.text((x, y+15), entity_name, fill=arrow_color, anchor="mm")
            
            # Draw separator line
            draw.line([x-entity_width//2, y+30, x+entity_width//2, y+30], fill=arrow_color, width=1)
            
            # Add some sample attributes
            attrs = ["id", "name", "attribute1", "attribute2"]
            for j, attr in enumerate(attrs):
                if j < 4:  # Limit to 4 attributes
                    draw.text((x-entity_width//2+20, y+45+j*18), attr, fill=arrow_color)
            
            # Connect entities with lines representing relationships
            if i < num_entities - 1:
                next_x = 50 + spacing * (i + 2)
                relationship_y = y + entity_height // 2
                
                # Draw the relationship line
                draw.line([x+entity_width//2, relationship_y, next_x-entity_width//2, relationship_y], 
                          fill=arrow_color, width=2)
                
                # Draw relationship name
                rel_name = "has" if i % 2 == 0 else "belongs to"
                rel_x = (x+entity_width//2 + next_x-entity_width//2) // 2
                draw.text((rel_x, relationship_y-15), rel_name, fill=arrow_color, anchor="mm")
                
                # Draw cardinality notations
                draw.text((x+entity_width//2+15, relationship_y), "1", fill=arrow_color, anchor="mm")
                draw.text((next_x-entity_width//2-15, relationship_y), "*", fill=arrow_color, anchor="mm")
    
    def _draw_gantt_chart(self, draw, mermaid_code, width, y_start, height, arrow_color, text_color, font):
        """Draw a simplified Gantt chart visualization.""" 
        # Parse task information from gantt chart
        tasks = re.findall(r'^\s*(.+?)\s*:.*$', mermaid_code, re.MULTILINE)
        if not tasks:
            tasks = ["Task 1", "Task 2", "Task 3", "Task 4"]
        
        # Limit to 5 tasks
        tasks = tasks[:5]
        
        # Find title
        title = re.search(r'title\s+(.+?)(?:\n|$)', mermaid_code)
        chart_title = title.group(1) if title else "Project Timeline"
        
        # Draw title
        draw.text((width//2, y_start+20), chart_title, fill=text_color, font=font, anchor="mm")
        
        # Gantt chart layout
        chart_x = 160
        chart_width = width - chart_x - 40
        chart_y = y_start + 60
        row_height = min(40, (height - 120) / len(tasks))
        
        # Draw timeline header
        header_y = chart_y - 30
        draw.text((chart_x - 10, header_y), "Tasks", fill=text_color, font=font, anchor="rm")
        
        # Draw time divisions (10 divisions)
        time_div_width = chart_width / 10
        for i in range(11):
            x = chart_x + i * time_div_width
            # Division line
            draw.line([x, chart_y, x, chart_y + len(tasks) * row_height], fill=arrow_color, width=1)
            # Time label
            if i < 10:  # Don't label the last division
                draw.text((x + time_div_width // 2, header_y), f"W{i+1}", fill=text_color, font=font, anchor="mm")
        
        # Draw horizontal separators
        for i in range(len(tasks) + 1):
            y = chart_y + i * row_height
            draw.line([chart_x, y, width - 40, y], fill=arrow_color, width=1)
        
        # Draw tasks
        for i, task in enumerate(tasks):
            # Task name
            task_y = chart_y + (i + 0.5) * row_height
            task_name = task[:15] + "..." if len(task) > 15 else task
            draw.text((chart_x - 10, task_y), task_name, fill=text_color, font=font, anchor="rm")
            
            # Task bar
            start = i * 0.8 + 1  # Randomize start position
            duration = min(random.uniform(2, 5), 10 - start)  # Randomize duration
            
            bar_x = chart_x + start * time_div_width
            bar_width = duration * time_div_width
            bar_y = chart_y + i * row_height + 5
            bar_height = row_height - 10
            
            # Draw task bar
            bar_color = (70, 130, 180)  # Steel blue
            draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], fill=bar_color, outline=arrow_color, width=1)
    
    def _draw_generic_diagram(self, draw, mermaid_code, width, y_start, height, arrow_color):
        """Draw a generic diagram visualization.""" 
        # Create a grid of shapes representing a generic diagram
        shapes = [
            ("rectangle", (width//4, y_start + height//4, width//4 + 120, y_start + height//4 + 60)),
            ("diamond", [(width//2, y_start + height//2 - 40), 
                         (width//2 + 60, y_start + height//2), 
                         (width//2, y_start + height//2 + 40), 
                         (width//2 - 60, y_start + height//2)]),
            ("rectangle", (width*3//4 - 60, y_start + height*3//4 - 30, width*3//4 + 60, y_start + height*3//4 + 30))
        ]
        
        # Draw shapes
        for shape_type, coords in shapes:
            if shape_type == "rectangle":
                draw.rectangle(coords, outline=arrow_color, width=2)
            elif shape_type == "diamond":
                draw.polygon(coords, outline=arrow_color, fill=(248, 250, 252), width=2)
        
        # Draw connecting lines
        draw.line([width//4 + 120, y_start + height//4 + 30, width//2 - 60, y_start + height//2], 
                  fill=arrow_color, width=2)
        draw.line([width//2 + 60, y_start + height//2, width*3//4 - 60, y_start + height*3//4], 
                  fill=arrow_color, width=2)
                  
        # Add arrowheads
        draw.polygon([width//2 - 60, y_start + height//2, 
                      width//2 - 70, y_start + height//2 - 5, 
                      width//2 - 70, y_start + height//2 + 5], fill=arrow_color)
                      
        draw.polygon([width*3//4 - 60, y_start + height*3//4, 
                      width*3//4 - 70, y_start + height*3//4 - 5, 
                      width*3//4 - 70, y_start + height*3//4 + 5], fill=arrow_color)
    
    def _optimize_image(self, image_path: str) -> bool:
        """Optimize the generated diagram image for PDF quality."""
        try:
            with Image.open(image_path) as img:
                # Ensure white background (convert transparent to white)
                if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                    # Create a new image with white background
                    background = Image.new('RGBA', img.size, (255, 255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, (0, 0), img)
                    img = background.convert('RGB')
                
                # Resize the image if it's too large (prevents memory issues in PDF)
                max_dimension = 2000
                if img.width > max_dimension or img.height > max_dimension:
                    ratio = min(max_dimension / img.width, max_dimension / img.height)
                    new_size = (int(img.width * ratio), int(img.height * ratio))
                    img = img.resize(new_size, Image.LANCZOS)
                
                # Improve image quality and save
                img.save(image_path, format="PNG", quality=95, optimize=True)
                return True
        except Exception as e:
            print(f"Error optimizing image: {e}")
            return False