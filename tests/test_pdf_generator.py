import os
import pytest
from pdf_report.components import (
    PDFDocument,
    TextComponent,
    TableComponent,
    ImageComponent,
    PageBreakComponent,
    TableColumn,
    TextAlignment,
)
from pdf_report.generator import generate_pdf

# Define the output directory for test PDFs
OUTPUT_DIR = "outputs"

@pytest.fixture(scope="module", autouse=True)
def create_output_dir():
    """Create the output directory before tests and clean up afterwards."""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    yield # Run the tests
    # Optional: Clean up generated files after tests
    # for filename in os.listdir(OUTPUT_DIR):
    #     if filename.startswith("test_report_") and filename.endswith(".pdf"):
    #         os.remove(os.path.join(OUTPUT_DIR, filename))

def test_generate_pdf_with_mock_data():
    """
    Tests PDF generation using a simple mock PDFDocument structure.
    """
    output_filename = os.path.join(OUTPUT_DIR, "test_report_mock.pdf")

    # Ensure the output file does not exist before the test
    if os.path.exists(output_filename):
        os.remove(output_filename)

    # Create mock data using the PDFDocument and component models
    mock_document = PDFDocument(
        components=[
            TextComponent(
                content="Sample Financial Report",
                style="heading1",
                alignment=TextAlignment.CENTER,
                space_after=18 # Add some space after the heading
            ),
            TextComponent(
                content="Report Date: 2025-04-26",
                alignment=TextAlignment.CENTER,
                space_after=24 # Add space after the date
            ),
            PageBreakComponent(), # Start a new page
            TextComponent(
                content="Executive Summary",
                style="heading1",
                space_after=12
            ),
            TextComponent(
                content=(
                    "This is a brief executive summary generated for testing purposes. "
                    "It demonstrates the rendering of a basic text paragraph with justification."
                ),
                style="body",
                alignment=TextAlignment.JUSTIFY,
                space_after=18
            ),
            TableComponent(
                title="Key Metrics",
                columns=[
                    TableColumn(header="Metric", data_key="metric"),
                    TableColumn(header="Value", data_key="value", alignment=TextAlignment.RIGHT),
                    TableColumn(header="Unit", data_key="unit", alignment=TextAlignment.CENTER)
                ],
                data=[
                    {"metric": "Total AuM", "value": "1,500,000.00", "unit": "USD"},
                    {"metric": "MTD Performance", "value": "+1.2%", "unit": "%"},
                    {"metric": "YTD Performance", "value": "+5.8%", "unit": "%"},
                ],
                # Add some space after the table
                # space_after is not directly supported by TableComponent in components.py,
                # but can be added via CSS or a following TextComponent with space_before
            ),
            # Add a placeholder image component - will likely fail unless a dummy image exists
            # For demonstration, we can skip this or ensure a dummy file exists.
            # Let's add a dummy image creation for the test for robustness.
            # First, create a simple dummy image file
            # import tempfile
            # import matplotlib.pyplot as plt
            # dummy_img_path = os.path.join(OUTPUT_DIR, "dummy_chart.png")
            # plt.figure(figsize=(4, 3))
            # plt.plot([0, 1, 2, 3], [0, 1, 4, 9])
            # plt.title("Dummy Chart")
            # plt.savefig(dummy_img_path)
            # plt.close()
            # ImageComponent(image_path=dummy_img_path, caption="Sample Chart (Dummy)"),

            PageBreakComponent(), # Another page break
            TextComponent(
                content="Appendix A: Detailed Data",
                style="heading1",
                space_after=12
            ),
            TextComponent(
                content="This section contains more detailed data points.",
                style="body"
            )
            # More components can be added here as needed for a comprehensive test
        ]
    )

    # Generate the PDF
    generate_pdf(mock_document, output_filename)

    # Assert that the PDF file was created
    assert os.path.exists(output_filename)

    # Optional: Check file size is greater than 0
    assert os.path.getsize(output_filename) > 0

    # Optional: Add cleanup for the dummy image if it was created
    # if os.path.exists(dummy_img_path):
    #     os.remove(dummy_img_path)
