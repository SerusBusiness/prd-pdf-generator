"""
PDF Generator module for creating the final PRD document
"""
import os
from pathlib import Path
import markdown
import textwrap
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, Flowable, KeepTogether
from reportlab.lib.units import inch, mm
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from prd_generator.core.config import Config
from PIL import Image as PILImage


class ImagePlaceholder(Flowable):
    """A flowable that creates a placeholder for an image that couldn't be loaded."""
    
    def __init__(self, width, height, description):
        Flowable.__init__(self)
        self.width = width
        self.height = height
        self.description = description
    
    def draw(self):
        """Draw the placeholder on the canvas."""
        # Draw box
        self.canv.setStrokeColor(colors.grey)
        self.canv.setFillColor(colors.lightgrey)
        self.canv.rect(0, 0, self.width, self.height, stroke=1, fill=1)
        
        # Draw text
        self.canv.setFillColor(colors.black)
        self.canv.setFont("Helvetica", 12)
        
        # Draw title
        title = "Image Placeholder"
        self.canv.drawCentredString(self.width / 2.0, self.height - 20, title)
        
        # Draw description with wrapped text
        text_obj = self.canv.beginText(10, self.height - 40)
        text_obj.setFont("Helvetica", 10)
        
        # Wrap text to fit inside the placeholder
        max_width = int(self.width / 7)  # Approximate characters per line
        wrapper = textwrap.TextWrapper(width=max_width)
        wrapped_desc = wrapper.fill(self.description)
        
        for line in wrapped_desc.split('\n'):
            text_obj.textLine(line)
            
        self.canv.drawText(text_obj)

    def wrap(self, availWidth, availHeight):
        return self.width, self.height


class SafeImage(Image):
    """An image wrapper that ensures it won't exceed page boundaries."""
    
    def wrap(self, availWidth, availHeight):
        # First check if image is too large for the available space
        if self.drawHeight > availHeight * 0.9:
            # Scale down to fit available height with some margin
            scale = (availHeight * 0.85) / self.drawHeight
            self.drawWidth *= scale
            self.drawHeight *= scale
            
        # Also ensure width isn't too large
        if self.drawWidth > availWidth:
            scale = availWidth / self.drawWidth
            self.drawWidth *= scale
            self.drawHeight *= scale
            
        return Image.wrap(self, availWidth, availHeight)


class FooterCanvas(Canvas):
    """Canvas implementation that adds a footer to each page."""
    
    def __init__(self, *args, **kwargs):
        self.footer_text = kwargs.pop('footer_text', "Powered by AI")
        self.timestamp = kwargs.pop('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M'))
        Canvas.__init__(self, *args, **kwargs)
        
    def drawPage(self, page):
        """Add the page with the footer at the bottom."""
        self._add_footer()
        page.drawOn(self, 0, 0)
        self.showPage()
        
    def _add_footer(self):
        """Draw footer on the canvas."""
        footer_text = self.footer_text
        timestamp = self.timestamp
        
        # Set font and size
        self.setFont('Helvetica', 8)
        
        # Calculate positions
        page_width = self._pagesize[0]
        page_height = self._pagesize[1]
        
        # Calculate text width to center it
        footer_width = stringWidth(footer_text, 'Helvetica', 8)
        timestamp_width = stringWidth(timestamp, 'Helvetica', 8)
        
        # Draw footer text on the left side
        self.setFillColor(colors.darkgrey)
        self.drawString(15, 20, footer_text)
        
        # Draw timestamp on the right side
        self.drawRightString(page_width - 15, 20, timestamp)


class PDFGenerator:
    """Generator for creating properly formatted PDF documents."""
    
    def __init__(self, config: Config):
        """Initialize the PDF generator with configuration."""
        self.config = config
        self.styles = getSampleStyleSheet()
        self.setup_styles()
        # Set max sizes based on A4 page
        self.max_image_width = self.config.page_width - (2 * self.config.margin) - 20  # 10pt margin on each side
        self.max_image_height = 500  # Max height in points (about 7 inches)
        
    def setup_styles(self):
        """Set up custom paragraph styles for the document."""
        # Title style - check if it exists first to avoid KeyError
        if 'PRDTitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='PRDTitle',
                parent=self.styles['Heading1'],
                fontSize=24,
                spaceAfter=30,
                alignment=1  # Center alignment
            ))
        
        # Section heading style
        if 'SectionHeading' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='SectionHeading',
                parent=self.styles['Heading2'],
                fontSize=16,
                spaceBefore=20,
                spaceAfter=10
            ))
        
        # Body text style
        if 'PRDBodyText' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='PRDBodyText',
                parent=self.styles['Normal'],
                fontSize=11,
                leading=14,  # Line spacing
                spaceBefore=6,
                spaceAfter=6
            ))
        
        # Reference style
        if 'Reference' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='Reference',
                parent=self.styles['PRDBodyText'] if 'PRDBodyText' in self.styles else self.styles['Normal'],
                fontSize=10,
                textColor=colors.blue
            ))
        
        # Image caption style
        if 'Caption' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='Caption',
                parent=self.styles['PRDBodyText'] if 'PRDBodyText' in self.styles else self.styles['Normal'],
                fontSize=10,
                alignment=1,  # Center alignment
                textColor=colors.darkblue
            ))
    
    def generate_pdf(self, prd_content: dict, output_path: str, image_files=None, diagram_files=None, references=None):
        """
        Generate a PDF document from the PRD content.
        
        Args:
            prd_content: Dictionary containing PRD content by section
            output_path: Path to save the PDF file
            image_files: List of image file dictionaries
            diagram_files: List of diagram file dictionaries
            references: List of reference dictionaries
        """
        if image_files is None:
            image_files = []
        if diagram_files is None:
            diagram_files = []
        if references is None:
            references = []
            
        # Create timestamp for footer
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
            
        # Create the document with custom canvas to add footer
        def make_canvas(*args, **kwargs):
            return FooterCanvas(*args, footer_text="Powered by AI", timestamp=timestamp, **kwargs)
        
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=self.config.margin,
            rightMargin=self.config.margin,
            topMargin=self.config.margin,
            bottomMargin=self.config.margin + 15  # Extra margin at bottom for footer
        )
        
        # Create content list
        content = []
        
        # Add title
        project_name = self._extract_project_name(prd_content)
        content.append(Paragraph(f"Product Requirements Document", self.styles['PRDTitle']))
        content.append(Paragraph(project_name, self.styles['PRDTitle']))
        content.append(Spacer(1, 0.5 * inch))
        
        # Keep track of references - we'll add them at the end if there's no References section
        found_references_section = False
        
        # Process each section
        for section in self.config.prd_sections:
            # Skip sections that don't have content
            if section not in prd_content:
                continue
                
            section_content = prd_content[section]
            # Check if section_content is empty (handle both string and dict cases)
            if isinstance(section_content, str):
                if not section_content.strip():
                    continue
            elif isinstance(section_content, dict):
                if not section_content:  # Empty dictionary
                    continue
            elif section_content is None:
                continue
            
            # Add a page break before each major section except the first one
            if section != self.config.prd_sections[0]:
                content.append(PageBreak())
            
            # Add section heading
            content.append(Paragraph(section, self.styles['SectionHeading']))
            
            # Process markdown text - ensure section_content is a string
            if isinstance(section_content, str):
                html = markdown.markdown(section_content)
                
                # Split HTML into paragraphs
                paragraphs = self._split_html_paragraphs(html)
                
                for p in paragraphs:
                    content.append(Paragraph(p, self.styles['PRDBodyText']))
                    content.append(Spacer(1, 0.1 * inch))
            elif isinstance(section_content, dict):
                # Handle dictionary content - convert each key-value pair to paragraphs
                for key, value in section_content.items():
                    if isinstance(value, str):
                        # Add subsection header if key is meaningful
                        if key not in ["content", "text"]:
                            content.append(Paragraph(key, self.styles['SectionHeading']))
                        
                        # Process the value as markdown
                        html = markdown.markdown(value)
                        paragraphs = self._split_html_paragraphs(html)
                        
                        for p in paragraphs:
                            content.append(Paragraph(p, self.styles['PRDBodyText']))
                            content.append(Spacer(1, 0.1 * inch))
            
            # Add images or diagrams related to this section
            section_images = [img for img in image_files if img.get('section') == section]
            section_diagrams = [diag for diag in diagram_files if diag.get('section') == section]
            
            # Combine images and diagrams for this section
            visual_items = section_images + section_diagrams
            
            # Add each visual with appropriate spacing and sizing
            for item in visual_items:
                # Add a page break before large diagrams to avoid layout issues
                if 'type' in item and item.get('type') in ['class', 'sequence', 'flowchart', 'gantt'] and len(visual_items) > 1:
                    content.append(PageBreak())
                    
                # Add the visual
                self._add_visual_to_content(content, item, is_diagram='type' in item)
                
                # Add some extra space after complex diagrams
                if 'type' in item and item.get('type') in ['class', 'sequence', 'flowchart']:
                    content.append(Spacer(1, 0.1 * inch))
            
            # Add references in the References section with improved formatting
            if section == "References":
                found_references_section = True
                # Add user-provided content from PRD first
                if section_content:
                    content.append(Spacer(1, 0.2 * inch))
                
                # Add external references with better formatting
                if references:
                    self._add_references_to_content(content, references)
        
        # If there was no References section but we have references, add them at the end
        if not found_references_section and references:
            content.append(PageBreak())
            content.append(Paragraph("References", self.styles['SectionHeading']))
            self._add_references_to_content(content, references)
        
        # Build the PDF with error handling
        try:
            doc.build(content, canvasmaker=make_canvas)
        except Exception as e:
            print(f"Error building PDF: {str(e)}")
            # Try rebuild with more conservative image sizing
            print("Attempting rebuild with conservative image sizing...")
            self.max_image_height = 350  # Reduce max height further
            
            # Rebuild content list with safer settings
            content = self._rebuild_content_list_safely(prd_content, image_files, diagram_files, references)
            doc.build(content, canvasmaker=make_canvas)
    
    def _rebuild_content_list_safely(self, prd_content, image_files, diagram_files, references):
        """Rebuild the content list with more conservative image sizing."""
        # This is similar to generate_pdf but with stricter limits on image sizes
        content = []
        
        # Add title
        project_name = self._extract_project_name(prd_content)
        content.append(Paragraph(f"Product Requirements Document", self.styles['PRDTitle']))
        content.append(Paragraph(project_name, self.styles['PRDTitle']))
        content.append(Spacer(1, 0.5 * inch))
        
        # Process each section
        for section in self.config.prd_sections:
            # Skip sections that don't have content
            if section not in prd_content:
                continue
                
            section_content = prd_content[section]
            # Check if section_content is empty (handle both string and dict cases)
            if isinstance(section_content, str):
                if not section_content.strip():
                    continue
            elif isinstance(section_content, dict):
                if not section_content:  # Empty dictionary
                    continue
            elif section_content is None:
                continue
            
            # Add a page break before each major section except the first one
            if section != self.config.prd_sections[0]:
                content.append(PageBreak())
            
            # Add section heading
            content.append(Paragraph(section, self.styles['SectionHeading']))
            
            # Process markdown text - ensure section_content is a string
            if isinstance(section_content, str):
                html = markdown.markdown(section_content)
                
                # Split HTML into paragraphs
                paragraphs = self._split_html_paragraphs(html)
                
                for p in paragraphs:
                    content.append(Paragraph(p, self.styles['PRDBodyText']))
                    content.append(Spacer(1, 0.1 * inch))
            elif isinstance(section_content, dict):
                # Handle dictionary content - convert each key-value pair to paragraphs
                for key, value in section_content.items():
                    if isinstance(value, str):
                        # Add subsection header if key is meaningful
                        if key not in ["content", "text"]:
                            content.append(Paragraph(key, self.styles['SectionHeading']))
                        
                        # Process the value as markdown
                        html = markdown.markdown(value)
                        paragraphs = self._split_html_paragraphs(html)
                        
                        for p in paragraphs:
                            content.append(Paragraph(p, self.styles['PRDBodyText']))
                            content.append(Spacer(1, 0.1 * inch))
            
            # Add images or diagrams related to this section
            section_images = [img for img in image_files if img.get('section') == section]
            section_diagrams = [diag for diag in diagram_files if diag.get('section') == section]
            
            # For each diagram/image, ensure it gets its own page
            for item in section_diagrams + section_images:
                content.append(PageBreak())
                self._add_visual_to_content_safely(content, item, is_diagram='type' in item)
            
            # Add references in the References section
            if section == "References" and references:
                content.append(Spacer(1, 0.2 * inch))
                content.append(Paragraph("External References:", self.styles['PRDBodyText']))
                
                for ref in references:
                    ref_text = f"{ref['title']} - <a href='{ref['url']}'>{ref['url']}</a>"
                    content.append(Paragraph(ref_text, self.styles['Reference']))
        
        return content
        
    def _extract_project_name(self, prd_content: dict) -> str:
        """Extract a project name from the PRD content."""
        if "Executive Summary" in prd_content:
            # Check if the executive summary is a string or a dictionary
            if isinstance(prd_content["Executive Summary"], str):
                # Try to get project name from first sentence of executive summary
                first_sentence = prd_content["Executive Summary"].split('.')[0]
                if "project" in first_sentence.lower():
                    return first_sentence
                
                # Or try first line
                first_line = prd_content["Executive Summary"].split('\n')[0]
                return first_line
            elif isinstance(prd_content["Executive Summary"], dict):
                # Handle the case when executive summary is a dictionary
                # Try to extract a title or summary field
                if "title" in prd_content["Executive Summary"]:
                    return prd_content["Executive Summary"]["title"]
                elif "summary" in prd_content["Executive Summary"]:
                    return prd_content["Executive Summary"]["summary"]
                # Return the first value in the dict if it's a string
                for value in prd_content["Executive Summary"].values():
                    if isinstance(value, str):
                        return value.split('.')[0]
        
        # Check other potential title locations
        if "Project Title" in prd_content and isinstance(prd_content["Project Title"], str):
            return prd_content["Project Title"]
        if "Introduction" in prd_content and isinstance(prd_content["Introduction"], str):
            return prd_content["Introduction"].split('.')[0]
        
        return "Product Requirements Document"
    
    def _split_html_paragraphs(self, html: str) -> list:
        """Split HTML content into individual paragraphs."""
        # Very simple HTML splitter - for complex HTML would need a proper parser
        paragraphs = []
        
        # Process list items
        html = html.replace('<li>', '<p>• ')
        html = html.replace('</li>', '</p>')
        
        # Remove lists
        html = html.replace('<ul>', '')
        html = html.replace('</ul>', '')
        html = html.replace('<ol>', '')
        html = html.replace('</ol>', '')
        
        # Split by paragraph tags
        parts = html.split('<p>')
        for part in parts:
            if '</p>' in part:
                p_content = part.split('</p>')[0].strip()
                if p_content:  # Skip empty paragraphs
                    paragraphs.append(p_content)
        
        return paragraphs
    
    def _add_visual_to_content(self, content, item_data, is_diagram=False):
        """Add an image or diagram to the document content with dynamic sizing."""
        content.append(Spacer(1, 0.2 * inch))
        
        try:
            # Get the path to the image
            image_path = item_data.get('path', '')
            
            if os.path.exists(image_path):
                try:
                    # First open with PIL to verify the image is valid and get dimensions
                    with PILImage.open(image_path) as pil_img:
                        original_width, original_height = pil_img.size
                        
                        # Prepare a valid image for ReportLab
                        with io.BytesIO() as img_bytes:
                            pil_img.save(img_bytes, format=pil_img.format or 'PNG')
                            img_bytes.seek(0)
                            # Create a temporary file with the right extension
                            temp_path = f"{image_path}.valid"
                            with open(temp_path, 'wb') as f:
                                f.write(img_bytes.read())
                    
                    # Try to create an Image object using the validated image
                    img = SafeImage(temp_path)
                    
                    # Available width accounting for margins
                    available_width = self.max_image_width
                    
                    # Determine optimal scaling based on image type and content
                    if is_diagram:
                        # Diagrams often need more space to be readable
                        diagram_type = item_data.get('type', '').lower()
                        
                        max_height = min(self.max_image_height, 350)  # Default max height for diagrams
                        
                        if 'sequence' in diagram_type:
                            # Sequence diagrams are typically wider than tall
                            max_height = min(self.max_image_height, 300)  # More restrictive height
                            width_scale = min(0.9, available_width / img.drawWidth)
                            height_scale = min(max_height / img.drawHeight, 1.0) 
                            scale_factor = min(width_scale, height_scale)
                        elif 'gantt' in diagram_type:
                            # Gantt charts need width
                            max_height = min(self.max_image_height, 250)
                            width_scale = min(0.95, available_width / img.drawWidth)
                            height_scale = min(max_height / img.drawHeight, 1.0) 
                            scale_factor = min(width_scale, height_scale)
                        elif 'class' in diagram_type:
                            # Class diagrams need space for details but must fit page
                            max_height = min(self.max_image_height, 300)
                            width_scale = min(0.9, available_width / img.drawWidth)
                            height_scale = min(max_height / img.drawHeight, 1.0)
                            scale_factor = min(width_scale, height_scale)
                        else:
                            # Default diagram scaling
                            width_scale = min(0.9, available_width / img.drawWidth)
                            height_scale = min(max_height / img.drawHeight, 1.0)
                            scale_factor = min(width_scale, height_scale)
                    else:
                        # Standard image sizing
                        width_scale = min(0.85, available_width / img.drawWidth)
                        height_scale = min(self.max_image_height / img.drawHeight, 1.0)
                        scale_factor = min(width_scale, height_scale)
                    
                    # Apply the scaling, ensuring we don't exceed maximum dimensions
                    img.drawWidth = min(img.drawWidth * scale_factor, available_width)
                    img.drawHeight = min(img.drawHeight * scale_factor, self.max_image_height)
                    
                    # Add the image to the content
                    content.append(img)
                    
                    # Clean up temporary file
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except:
                            pass
                except Exception as img_err:
                    print(f"Error adding image to PDF: {img_err}")
                    # If ReportLab can't handle the image, create a placeholder
                    desc = item_data.get('description', item_data.get('title', 'Image'))
                    if is_diagram:
                        desc = f"{item_data.get('title', 'Diagram')}"
                    
                    # Size the placeholder appropriately
                    if is_diagram:
                        placeholder = ImagePlaceholder(available_width * 0.8, 200, desc)
                    else:
                        placeholder = ImagePlaceholder(available_width * 0.7, 150, desc)
                        
                    content.append(placeholder)
            else:
                # If the image file doesn't exist, create a placeholder
                desc = item_data.get('description', item_data.get('title', 'Image'))
                if is_diagram:
                    desc = f"{item_data.get('title', 'Diagram')}"
                    
                available_width = self.max_image_width
                placeholder = ImagePlaceholder(available_width * 0.75, 200, desc)
                content.append(placeholder)
            
            # Add caption
            if is_diagram:
                diagram_type = item_data.get('type', 'Diagram')
                caption = f"Figure: {item_data.get('title', 'Diagram')} ({diagram_type})"
            else:
                caption = f"Figure: {item_data.get('description', 'Image')}"
                
            content.append(Paragraph(caption, self.styles['Caption']))
            content.append(Spacer(1, 0.2 * inch))
        except Exception as e:
            print(f"Error handling image in PDF: {e}")
            # Add a text message indicating the error
            error_msg = f"[Could not include {'diagram' if is_diagram else 'image'}: {item_data.get('description', item_data.get('title', 'Image'))}]"
            content.append(Paragraph(error_msg, self.styles['PRDBodyText']))
            content.append(Spacer(1, 0.1 * inch))
    
    def _add_visual_to_content_safely(self, content, item_data, is_diagram=False):
        """Add an image or diagram to the document with ultra-conservative sizing."""
        content.append(Spacer(1, 0.2 * inch))
        
        try:
            # Get the path to the image
            image_path = item_data.get('path', '')
            
            if os.path.exists(image_path):
                try:
                    # First open with PIL to verify the image is valid and get dimensions
                    with PILImage.open(image_path) as pil_img:
                        # Resize the image to safe dimensions (max 450pt width, 300pt height)
                        safe_width = 450
                        safe_height = 300
                        
                        # Create a new image with white background
                        resized_img = PILImage.new("RGB", (safe_width, safe_height), (255, 255, 255))
                        
                        # Calculate scaling to fit within safe dimensions while preserving aspect ratio
                        width_ratio = safe_width / pil_img.width
                        height_ratio = safe_height / pil_img.height
                        scale_factor = min(width_ratio, height_ratio)
                        
                        new_width = int(pil_img.width * scale_factor)
                        new_height = int(pil_img.height * scale_factor)
                        
                        # Resize original image
                        resized_original = pil_img.resize((new_width, new_height), PILImage.LANCZOS)
                        
                        # Paste into center of new image
                        paste_x = (safe_width - new_width) // 2
                        paste_y = (safe_height - new_height) // 2
                        resized_img.paste(resized_original, (paste_x, paste_y))
                        
                        # Save resized image
                        temp_path = f"{image_path}.safe.png"
                        resized_img.save(temp_path)
                    
                    # Create a reportlab image
                    img = Image(temp_path)
                    
                    # Add the image to content
                    content.append(img)
                    
                    # Clean up temporary file
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except:
                            pass
                except Exception as img_err:
                    print(f"Error adding safe image to PDF: {img_err}")
                    # Use a very small placeholder
                    desc = item_data.get('description', item_data.get('title', 'Image'))
                    placeholder = ImagePlaceholder(400, 200, desc)
                    content.append(placeholder)
            else:
                # Create a small placeholder for missing images
                desc = item_data.get('description', item_data.get('title', 'Image'))
                placeholder = ImagePlaceholder(400, 200, desc)
                content.append(placeholder)
            
            # Add caption
            if is_diagram:
                diagram_type = item_data.get('type', 'Diagram')
                caption = f"Figure: {item_data.get('title', 'Diagram')} ({diagram_type})"
            else:
                caption = f"Figure: {item_data.get('description', 'Image')}"
                
            content.append(Paragraph(caption, self.styles['Caption']))
            content.append(Spacer(1, 0.2 * inch))
        except Exception as e:
            print(f"Error handling image in PDF: {e}")
            error_msg = f"[Could not include {'diagram' if is_diagram else 'image'}: {item_data.get('description', item_data.get('title', 'Image'))}]"
            content.append(Paragraph(error_msg, self.styles['PRDBodyText']))
            content.append(Spacer(1, 0.1 * inch))

    def _add_references_to_content(self, content, references):
        """Add formatted external references to the content with proper styling."""
        if not references:
            return
            
        content.append(Spacer(1, 0.3 * inch))
        content.append(Paragraph("External References:", self.styles['SectionHeading']))
        
        # Create a more visually distinct reference style just for external links
        external_ref_style = ParagraphStyle(
            name='ExternalReference',
            parent=self.styles['Reference'],
            fontSize=10,
            leftIndent=20,
            spaceBefore=8,
            spaceAfter=8,
            textColor=colors.blue,
            bulletIndent=10,
            bulletText='•'
        )
        
        # Group references by type if available
        grouped_refs = {}
        for ref in references:
            ref_type = ref.get('type', 'Other')
            if ref_type not in grouped_refs:
                grouped_refs[ref_type] = []
            grouped_refs[ref_type].append(ref)
        
        # Add references by group
        for ref_type, refs in grouped_refs.items():
            # Add the reference type as a subheading
            content.append(Spacer(1, 0.1 * inch))
            content.append(Paragraph(f"{ref_type}:", self.styles['PRDBodyText']))
            
            # Add each reference with bullet points and proper formatting
            for ref in refs:
                ref_title = ref.get('title', 'Reference')
                ref_url = ref.get('url', '')
                description = ref.get('description', '')
                
                if description:
                    ref_text = f"<b>{ref_title}</b> - {description}<br/><a href='{ref_url}' color='blue'>{ref_url}</a>"
                else:
                    ref_text = f"<b>{ref_title}</b><br/><a href='{ref_url}' color='blue'>{ref_url}</a>"
                    
                content.append(Paragraph(ref_text, external_ref_style))
        
        return content