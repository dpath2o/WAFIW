# Antarctic Fast Ice Watch: research demonstration

Compile locally: pdflatex main.tex twice, from this directory. Edit the single classification macro to replace both centred red warnings with OFFICIAL when appropriate.

The primary graphic uses the supplied RGB array and predicted TIFF for 10-22 October 2021. Class 2 changes from blue to green for display only; class values are unchanged. Class 0 is pack/ocean; class 1 combines masked land/ice shelf and out-of-swath areas. The supplied mask is not a verified coastline. No class 3 occurs in the downsampled display.

Source EPSG:3031; pixel size 40 m; bounds (-48395.993, -1625974.312, 361044.007, -1125614.312). The display downsamples classification by nearest neighbour to the RGB dimensions (1251 x 1024), reprojects both panels to Antarctic polar stereographic with central longitude 173.51759 E, and trims 12 km from the western bounding box. Southern extent is retained. North is aligned on the central meridian, not everywhere.

The broad southern masked region includes the Ross Ice Shelf. The previous Victoria Land label was misplaced over ice shelf and has been removed. Grounded features are labelled specifically as Ross Island and Minna Bluff; the latter projects from Mount Discovery. Faint outlines on both panels identify grounded land. These are geographical reference outlines, not an inferred border between named Antarctic regions. The arrow identifies the dominant McMurdo candidate fast-ice component; no additional coastal feature is invented.

Reproduce with numpy, rasterio, pyproj, matplotlib, scipy, shapely and pillow: python scripts/render_fastice.py INPUT_DIRECTORY assets. Original inputs: rgb_image_20211010_20211022.npy and predicted_map_20211010_20211022.tif (not bundled).

The composite is multi-scale processed SAR texture, not unprocessed backscatter. This extent-classification example does not show change or establish validation/operational readiness. Alex should confirm code provenance and interpretation.

The SWOT image is the original research plot of detrended sea-surface-height anomaly, not validated freeboard; the PDF caption states this distinction.

Coastline reference: SCAR Antarctic Digital Database (ADD), high resolution vector polygons v7.12, 2026, doi:10.5285/13c4d2f1-8903-4d7f-8977-592121975554. CC BY 4.0; data from the SCAR Antarctic Digital Database, 2026. A clipped and generalized EPSG:3031 subset is bundled as assets/ADD_coastline_subset_EPSG3031.geojson. Outlines are contextual, not 2021 contemporaneous boundaries. Only land polygon boundaries are drawn; artificial clipping edges are omitted.

Name source: SCAR Composite Gazetteer via AADC, Minna Bluff (US gazetteer ID 128940), 78 degrees 31 minutes S, 166 degrees 25 minutes E; narrative identifies a peninsula projecting from Mount Discovery into the Ross Ice Shelf.
