# --- PDF Report Generator ---

from typing import List, Dict, Any, Optional
from weasyprint import HTML
from .components import PDFDocument, PDFContentComponent, TextComponent, TableComponent, ImageComponent, PageBreakComponent

def render_component_to_html(component: PDFContentComponent) -> str:
    """Renders a single PDF content component into HTML."""
    if isinstance(component, TextComponent):
        # Simple text rendering, could be extended to handle markdown/styles
        style = f"text-align: {component.alignment.value};" if component.alignment else ""
        style += f"margin-top: {component.space_before}pt;" if component.space_before is not None else ""
        style += f"margin-bottom: {component.space_after}pt;" if component.space_after is not None else ""
        # Basic styling based on component.style
        if component.style == 'heading1':
            return f"<h1 style='{style}'>{component.content}</h1>"
        elif component.style == 'body':
             return f"<p style='{style}'>{component.content}</p>"
        elif component.style == 'bold':
             return f"<strong style='{style}'>{component.content}</strong>"
        elif component.style == 'italic':
             return f"<em style='{style}'>{component.content}</em>"
        else: # Default paragraph
            return f"<p style='{style}'>{component.content}</p>"

    elif isinstance(component, TableComponent):
        html = f"<table>"
        if component.title:
            html += f"<caption>{component.title}</caption>"
        html += "<thead><tr>"
        for col in component.columns:
            col_style = f"text-align: {col.alignment.value};" if col.alignment else ""
            html += f"<th style='{col_style}'>{col.header}</th>"
        html += "</tr></thead>"
        html += "<tbody>"
        for row in component.data:
            html += "<tr>"
            for col in component.columns:
                cell_data = row.get(col.data_key, "")
                cell_style = f"text-align: {col.alignment.value};" if col.alignment else ""
                html += f"<td style='{cell_style}'>{cell_data}</td>"
            html += "</tr>"
        html += "</tbody></table>"
        # Add basic table styling (borders, padding) via CSS later
        return html

    elif isinstance(component, ImageComponent):
        style = ""
        if component.width:
            style += f"width: {component.width}pt;"
        if component.height:
            style += f"height: {component.height}pt;"
        if component.alignment == TextAlignment.CENTER:
             style += "display: block; margin-left: auto; margin-right: auto;"
        # Add other alignments later
        img_tag = f"<img src='file://{component.image_path}' style='{style}'/>"
        if component.caption:
            return f"<figure>{img_tag}<figcaption>{component.caption}</figcaption></figure>"
        return img_tag

    elif isinstance(component, PageBreakComponent):
        return "<div style='page-break-after: always;'></div>"

    return "" # Handle unknown component types


def generate_pdf(pdf_document: PDFDocument, output_path: str):
    """
    Generates a PDF file from a PDFDocument object using WeasyPrint.
    """
    html_content = "<!DOCTYPE html><html><head><title>Financial Report</title>"
    # Add basic CSS for layout, margins, fonts here
    html_content += """
    <style>
        body { font-family: sans-serif; margin: 1in; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 1em; }
        th, td { border: 1px solid #ddd; padding: 8px; }
        th { text-align: left; }
        img { max-width: 100%; } /* Ensure images don't overflow */
    </style>"""
    html_content += "</head><body>"

    for component in pdf_document.components:
        html_content += render_component_to_html(component)

    html_content += "</body></html>"

    # Generate PDF using WeasyPrint
    HTML(string=html_content).write_pdf(output_path)

    print(f"PDF generated successfully at {output_path}")

# Example usage (can be removed or commented out for library use)
if __name__ == "__main__":
    from .components import TextAlignment, TextComponent, TableColumn, TableComponent, ImageComponent, PageBreakComponent, PDFDocument

    # Create a dummy PDFDocument
    dummy_document = PDFDocument(
        components=[
            TextComponent(content="Financial Report Cover Page", style="heading1", alignment=TextAlignment.CENTER),
            TextComponent(content="Report Date: 2025-04-26", alignment=TextAlignment.CENTER),
            PageBreakComponent(),
            TextComponent(content="Executive Summary", style="heading1"),
            TextComponent(content="This is a sample executive summary. It provides an overview of the report.", style="body", alignment=TextAlignment.JUSTIFY),
            TableComponent(
                title="Sample Data Table",
                columns=[
                    TableColumn(header="Metric", data_key="metric"),
                    TableColumn(header="Value", data_key="value", alignment=TextAlignment.RIGHT)
                ],
                data=[
                    {"metric": "Total AuM", "value": "1,234,567.89"},
                    {"metric": "MTD Performance", "value": "-0.5%"},
                ]
            ),
            ImageComponent(image_path="/path/to/a/sample/chart.png", caption="Sample Performance Chart"),
            PageBreakComponent(),
            TextComponent(content="Appendix", style="heading1"),
            TextComponent(content="More details can be found in the following pages.", style="body")
        ]
    )

    # Note: Replace with a valid path on your system if you run this example
    # For now, we are just defining the structure.
    # generate_pdf(dummy_document, "outputs/sample_report.pdf")
