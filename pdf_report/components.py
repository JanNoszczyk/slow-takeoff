# --- Pydantic Models for PDF Content Components ---

from typing import List, Dict, Any, Optional, Union, Literal
from pydantic import BaseModel, Field
from enum import Enum

class TextAlignment(str, Enum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFY = "justify"

class TextComponent(BaseModel):
    """Represents a block of text content for the PDF."""
    type: Literal["text"] = "text" # Discriminator field
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
    type: Literal["table"] = "table" # Discriminator field
    title: Optional[str] = None # Optional title for the table
    columns: List[TableColumn] # Definition of table columns
    data: List[Dict[str, Any]] # List of dictionaries, each representing a row
    # Add styling options later (e.g., borders, row colors)

class ImageComponent(BaseModel):
    """Represents an image (like a chart or logo) for the PDF."""
    type: Literal["image"] = "image" # Discriminator field
    image_path: str # Path to the image file (PNG, JPG, SVG)
    width: Optional[float] = None # Desired width in points
    height: Optional[float] = None # Desired height in points
    alignment: Optional[TextAlignment] = None # Alignment of the image on the page
    caption: Optional[str] = None # Optional caption for the image

class PageBreakComponent(BaseModel):
    """Forces a page break in the PDF."""
    type: Literal["page_break"] = "page_break" # Discriminator field

# Union of all possible content components
PDFContentComponent = Union[TextComponent, TableComponent, ImageComponent, PageBreakComponent]

class PDFDocument(BaseModel):
    """Represents the structure of the entire PDF document as a list of components."""
    components: List[PDFContentComponent] # Ordered list of components to render
    # Add document-level settings later (e.g., margins, headers/footers, title)
