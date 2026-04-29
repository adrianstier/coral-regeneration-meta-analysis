# Digitization Workspace

Use `pipeline/DIGITIZATION_FIGURE_QUEUE.csv` as the working manifest for figure and table extraction.

## Directories

- `figures/` - clipped source panels or tables from PDFs.
- `data/` - digitized point data or table transcriptions.

## Required Provenance

Every completed digitization task must record these fields in the queue:

- printed figure or table label
- PDF page
- panel label
- x-axis and y-axis labels
- units
- variance type
- sample-size source
- clip path
- digitized-data path
- digitizer
- QA reviewer
- QA status
- extraction notes

Do not use a figure-derived value in a pooled table until the queue row has a source clip and a digitized-data file.
