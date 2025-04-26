## Financial PDF Report Framework Design - PDF Composition Approach

This document outlines a revised design focusing specifically on the **PDF Generation** layer, allowing for the composition of a PDF from various content components.

### 1. PDF Content Component Models

To enable flexible PDF composition, we define Pydantic models representing different types of content elements that can be rendered by the PDF generation layer. These models capture the data and basic presentation hints for each component.

```python
# Example Pydantic models for PDF Content Components

from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum

class TextAlignment(str, Enum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFY = "justify"

class TextComponent(BaseModel):
    """Represents a block of text content for the PDF."""
    type: str = Field("text", const=True) # Discriminator field
    content: str # The actual text string, can include markdown or HTML depending on renderer capabilities
    style: Optional[str] = None # e.g., 'heading1', 'body', 'bold', 'italic' - maps to PDF styles
    alignment: Optional[TextAlignment] = None # Text alignment within the block
    space_before: Optional[float] = None # Vertical space before this component (in points)
    space_after: Optional[float] = None # Vertical space after this component (in points)

class TableColumn(BaseModel):
    """Represents a single column definition for a table."""
    header: str # Column header text
    data_key: str # Key to extract data for this column from each row dict
    width: Optional[float] = None # Column width (in points or percentage)
    alignment: Optional[TextAlignment] = None # Text alignment within the column cells
    # Add formatting options later if needed (e.g., number format, date format)

class TableComponent(BaseModel):
    """Represents a table for the PDF."""
    type: str = Field("table", const=True) # Discriminator field
    title: Optional[str] = None # Optional title for the table
    columns: List[TableColumn] # Definition of table columns
    data: List[Dict[str, Any]] # List of dictionaries, each representing a row
    # Add styling options later (e.g., borders, row colors)

class ImageComponent(BaseModel):
    """Represents an image (like a chart or logo) for the PDF."""
    type: str = Field("image", const=True) # Discriminator field
    image_path: str # Path to the image file (PNG, JPG, SVG)
    width: Optional[float] = None # Desired width in points
    height: Optional[float] = None # Desired height in points
    alignment: Optional[TextAlignment] = None # Alignment of the image on the page
    caption: Optional[str] = None # Optional caption for the image

class PageBreakComponent(BaseModel):
    """Forces a page break in the PDF."""
    type: str = Field("page_break", const=True) # Discriminator field

# Union of all possible content components
PDFContentComponent = Union[TextComponent, TableComponent, ImageComponent, PageBreakComponent]

class PDFDocument(BaseModel):
    """Represents the structure of the entire PDF document as a list of components."""
    components: List[PDFContentComponent] # Ordered list of components to render
    # Add document-level settings later (e.g., margins, headers/footers, title)

```

### 2. PDF Generation Layer - Composition Logic

*   **Purpose:** To iterate through a list of `PDFContentComponent` models (`PDFDocument.components`) and render each one sequentially into a PDF document, handling layout, styling, and pagination.

*   **Potential Technologies (Python):**
    *   **ReportLab:** Suitable for programmatic drawing. It would involve mapping each `PDFContentComponent` to corresponding ReportLab Flowables (Paragraph, Table, Image, PageBreak) and building a ReportLab Story. This provides fine-grained control but requires manual layout logic.
    *   **WeasyPrint:** Ideal for a templating approach. The list of components can be passed to an HTML template (e.g., using Jinja2). The template would loop through the components, rendering HTML/CSS for each type. WeasyPrint then converts the resulting HTML/CSS to PDF, handling layout automatically based on CSS. This approach is often faster for complex layouts and leverages web development skills.

*   **Key Functions:**
    *   `render_pdf(pdf_document: PDFDocument, output_path: str, template_path: Optional[str] = None)`: The main function that takes the `PDFDocument` object and the output file path. It will process the `components` list.
    *   `render_component(pdf_document, component: PDFContentComponent)`: A dispatcher function that determines the type of component and calls the appropriate rendering sub-function (e.g., `render_text`, `render_table`, `render_image`, `render_page_break`).
    *   `render_text(pdf_document, text_component: TextComponent)`: Adds text content to the PDF, applying style and alignment.
    *   `render_table(pdf_document, table_component: TableComponent)`: Formats and adds a table to the PDF.
    *   `render_image(pdf_document, image_component: ImageComponent)`: Embeds an image, potentially resizing and aligning it. This would likely involve a dependency on a charting/image generation library if the image_path points to a chart specification rather than a pre-rendered image file. Given the user's previous request about plotting, the Content Assembly layer would ideally generate the image file and provide the path here.
    *   `render_page_break(pdf_document, page_break_component: PageBreakComponent)`: Inserts a new page.

*   **Layout Composition:**
    *   The PDF Generation layer processes the components in the order they appear in the `PDFDocument.components` list.
    *   Each component's rendering function handles its specific visual representation and contributes to the overall document flow.
    *   Spacing and alignment defined in the component models are applied during rendering.
    *   PDF library features for pagination will handle page breaks automatically when content exceeds page boundaries, in addition to explicit page breaks inserted via `PageBreakComponent`.

This compositional approach provides flexibility. The Content Assembly layer (or any other data source) can generate a list of `PDFContentComponent` objects based on the required report sections and data, and the PDF Generation layer simply focuses on rendering this list into a PDF.
