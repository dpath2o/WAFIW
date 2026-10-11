"""Separate PyGMT maps and GIS rasters; panel assembly belongs to products."""
from pathlib import Path
import tempfile
import numpy as np
import rasterio
from rasterio.enums import ColorInterp
from rasterio.transform import from_bounds
from rasterio.warp import reproject, Resampling
from afiw.processing.raster import profile, load_exclusions, exclusion_mask
from afiw.processing.texture import rgb_texture

PALETTE     = np.full((256, 3), 235, dtype=np.uint8)
PALETTE[0]  = [15, 35, 48]
PALETTE[1]  = [88, 94, 99]
PALETTE[2]  = [68, 218, 100]
PALETTE[3]  = [240, 170, 40]
CLASS_NAMES = {0   : 'Other observed ocean / pack',
               1   : 'Excluded land / shelf',
               2   : 'Candidate fast ice (class 2)',
               3   : 'Candidate melt-affected fast ice',
               255 : 'No observation / unassigned'}

def require_pygmt():
    try:
        import pygmt
        with pygmt.clib.Session() as session:
            session.info
    except (ImportError, OSError) as error:
        raise RuntimeError('PyGMT/GMT unavailable. Install conda-forge pygmt, gmt and ghostscript; see docs/primary_maps.md') from error
    return pygmt

def export_composite(texture, destination, coastline=None):
    """Full texture-resolution RGBA; missing observations remain transparent."""
    destination = Path(destination)
    with rasterio.open(texture) as src:
        grid   = {key: getattr(src, key) for key in ('crs', 'transform', 'width', 'height')}
        shapes = load_exclusions(coastline, src.crs)
        with rasterio.open(destination, 'w', **profile(grid, count = 4, dtype = 'uint8', nodata = None)) as dst:
            for _, window in src.block_windows(1):
                rgb, valid    = rgb_texture(src.read(window = window, masked = True).filled(np.nan))
                excluded      = exclusion_mask(shapes, grid, window)
                rgb[excluded] = PALETTE[1]
                alpha         = np.where(valid | excluded, 255, 0).astype('uint8')
                dst.write(np.concatenate([np.moveaxis(rgb, -1, 0), alpha[None]], axis = 0), window = window)
            dst.colorinterp = (ColorInterp.red, ColorInterp.green, ColorInterp.blue, ColorInterp.alpha)
            dst.update_tags(product        = 'multi_scale_SAR_texture_RGB',
                            texture_range  = '[-0.5,1] clipped to [0,255]',
                            alpha          = '0 = unobserved; 255 = observed or excluded land/shelf',
                            source_texture = str(Path(texture).resolve()))
    return destination

def export_classification(classes, grid, destination):
    if classes.dtype != np.uint8 or not np.isin(classes, [0, 1, 2, 3, 255]).all():
        raise ValueError('Classification requires uint8 codes 0,1,2,3,255')
    destination = Path(destination)
    with rasterio.open(destination, 'w', **profile(grid, dtype = 'uint8', nodata = 255)) as dst:
        dst.write(classes, 1)
        dst.write_colormap(1, {i: (*map(int, PALETTE[i]), 0 if i == 255 else 255) for i in range(256)})
        dst.set_band_description(1, 'candidate ice classification')
        dst.update_tags(class_codes = ';'.join(f'{key} = {value}' for key, value in CLASS_NAMES.items()), status = 'candidate_classification', validated = 'false')
    return destination

def export_classification_rgb(classification, destination):
    with rasterio.open(classification) as src:
        grid = {key: getattr(src, key) for key in ('crs', 'transform', 'width', 'height')}
        with rasterio.open(destination, 'w', **profile(grid, count=4, dtype='uint8', nodata=None)) as dst:
            for _, window in src.block_windows(1):
                classes = src.read(1, window=window)
                if not np.isin(classes, [0, 1, 2, 3, 255]).all():
                    raise ValueError('Unknown classification code')
                rgba = np.concatenate([np.moveaxis(PALETTE[classes], -1, 0), np.where(classes == 255, 0, 255).astype('uint8')[None]], axis = 0)
                dst.write(rgba, window = window)
            dst.colorinterp = (ColorInterp.red, ColorInterp.green, ColorInterp.blue, ColorInterp.alpha)
            dst.update_tags(product = 'classification_display_RGBA', source = str(Path(classification).resolve()))
    return Path(destination)

def _geographic_image(source, destination, bbox, max_dimension=1800):
    """Temporary nearest-neighbour display reprojection, never analytical data."""
    west, south, east, north = bbox
    ratio  = (east - west) / (north - south)
    width  = max_dimension if ratio >= 1 else max(2, round(max_dimension * ratio))
    height = max(2, round(width / ratio))
    grid   = dict(crs = 'EPSG:4326', transform = from_bounds(west, south, east, north, width, height), width = width, height = height)
    with rasterio.open(source) as src, rasterio.open(destination, 'w', **profile(grid, count = 3, dtype = 'uint8', nodata = None)) as dst:
        # Raster alpha is converted into neutral background for stable GMT versions.
        rgba = np.zeros((4, height, width), dtype=np.uint8)
        for band in range(4):
            reproject(rasterio.band(src, band + 1), rgba[band],
                      src_transform = src.transform,
                      src_crs       = src.crs,
                      dst_transform = grid['transform'],
                      dst_crs       = grid['crs'],
                      resampling    = Resampling.nearest)
        rgba[:3, rgba[3] == 0] = 235
        dst.write(rgba[:3])
        dst.colorinterp = (ColorInterp.red, ColorInterp.green, ColorInterp.blue)
    return destination

def map_figure(raster, path, region, title, subtitle, classification=False):
    """PyGMT stereographic map with lon/lat graticule, station and legend."""
    pygmt      = require_pygmt()
    path       = Path(path)
    west, south, east, north = region.bbox
    lon0       = (west + east) / 2
    projection = f'S{lon0}/{-90 if (south + north) < 0 else 90}/16c'
    map_region = [west, east, south, north]
    with tempfile.TemporaryDirectory(prefix='afiw_gmt_') as tmp:
        image = _geographic_image(raster, Path(tmp) / 'display.tif', region.bbox)
        fig   = pygmt.Figure()
        with pygmt.config(MAP_FRAME_TYPE       = 'plain',
                          FORMAT_GEO_MAP       = 'ddd.xxF',
                          FONT_ANNOT_PRIMARY   = '10p,Helvetica',
                          FONT_LABEL           = '11p,Helvetica',
                          FONT_TITLE           = '12p,Helvetica',
                          MAP_GRID_PEN_PRIMARY = '0.2p,gray50,-'):
            fig.grdimage(grid = str(image), region = map_region, projection = projection, interpolation = 'n', dpi = 200)
            fig.basemap(frame = ['WSne+t' + title, 'xafg+lLongitude', 'yafg+lLatitude'])
            if west <= region.station_lon <= east and south <= region.station_lat <= north:
                fig.plot(x = [region.station_lon], y = [region.station_lat], style = 't0.23c', fill = 'red', pen = '0.5p,white')
                fig.text(x = region.station_lon, y = region.station_lat, text = region.name,
                         font = '10p,Helvetica-Bold,black', justify = 'BL', offset = '0.15c/0.15c', fill = 'white@20', clearance = '0.04c')
            # Legend is in page coordinates, outside the geographic map frame.
            rows = ['H 9p,Helvetica-Bold Map key']
            if classification:
                rows += [f'S 0.15c s 0.18c {"/".join(map(str, PALETTE[i]))} 0.25p 0.35c {CLASS_NAMES[i]}' for i in (0, 2, 3)]
            else:
                rows += ['L 9p,Helvetica L RGB: three NormProd texture scales']
            rows += ['S 0.15c s 0.18c 88/94/99 0.25p 0.35c Excluded land / shelf',
                     'S 0.15c s 0.18c 235/235/235 0.25p 0.35c No observation / unassigned',
                     'S 0.15c t 0.18c red 0.25p 0.35c Station',
                     'L 8p,Helvetica L ' + subtitle,
                     'L 8p,Helvetica L RESEARCH DEMONSTRATION - NOT FOR OPERATIONAL USE']
            legend = Path(tmp) / 'legend.txt'
            legend.write_text('\n'.join(rows) + '\n')
            fig.legend(spec=str(legend), position='JBC+w16c/3.6c+o0c/0.9c', box='+gwhite+p0.25p')
            fig.savefig(str(path), dpi=200, crop='+m0.2c')
    return path

def render_maps(composite, classification, directory, region, first_time, second_time, synthetic=False, windows=(11, 21, 33)):
    directory     = Path(directory)
    title         = f'{region.name}: {first_time[:10]} to {second_time[:10]}'
    subtitle      = 'SYNTHETIC TEST DATA' if synthetic else 'SAR observations; unvalidated research product'
    composite_png = map_figure(composite, directory / 'composite.png', region, 'Composite SAR texture | ' + title, subtitle + '; RGB windows ' + '/'.join(map(str, windows)))
    outputs       = {'composite_png': composite_png.name, 'composite_tif': Path(composite).name}
    if classification:
        display = export_classification_rgb(classification, directory / 'classification_rgb.tif')
        png     = map_figure(display, directory / 'classification.png', region, 'Candidate classification | ' + title, subtitle, classification = True)
        outputs.update(classification = Path(classification).name, classification_png = png.name, classification_rgb_tif = display.name)
    return outputs
