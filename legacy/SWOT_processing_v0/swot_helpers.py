#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Helper functions to work with swot data


"""

import os
import geopandas as gpd
from shapely import geometry
import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from getpass import getpass
import ftplib
from urllib.parse import urlparse
import xarray as xr
from concurrent.futures import ThreadPoolExecutor, as_completed



# --------------------------------------------------------------------------- # 
# --------------------------------------------------------------------------- # 

def get_half_orbits_intersect(bbox):
    """Get half orbits that intersect a bounding box.

    Parameters
    ----------
    bbox: 
        the bounding box
        
    Returns
    -------
     gpd.GeoDataFrame:
        A Geopandas dataframe containing intersecting half orbits numbers and geometries
    """
    swath_geometries = gpd.read_file(GEOMETRIES_FILE)

    bbox_polygon = geometry.box(*bbox)

    def _filter_intersect(row, polygon):
        half_orbit_polygon = row.geometry
        return polygon.intersects(half_orbit_polygon)

    select = swath_geometries.apply(_filter_intersect, polygon=bbox_polygon, axis=1)
    return swath_geometries[select]

# --------------------------------------------------------------------------- # 

def plot_geometries(geometries, lon_range, lat_range, title, plot_extent=None):
    fig, ax = plt.subplots(ncols=1, figsize=(12, 8), subplot_kw={'projection': ccrs.PlateCarree()})

    gpd.GeoSeries(geometries.geometry).plot(ax=ax,transform=ccrs.PlateCarree(),alpha=1)
    
    square = patches.Rectangle((lon_range[0], lat_range[0]), lon_range[1]-lon_range[0], lat_range[1]-lat_range[0], edgecolor='orange', facecolor='none', transform=ccrs.PlateCarree())
    ax.add_patch(square)

    ax.set_title(title)
    ax.coastlines()
    if plot_extent:
        ax.set_extent(plot_extent, crs=ccrs.PlateCarree())

# --------------------------------------------------------------------------- # 

def _download_file_thread(ftp_details, ftp_path, filename, target_directory, max_retries=3):
    """Download a single file with a new FTP connection (thread-safe), skip if exists, retry on failure."""
    ftp_host, username, password = ftp_details
    local_filepath = os.path.join(target_directory, filename)

    if os.path.exists(local_filepath):
        print(f"Skipping {filename}, already exists.")
        return local_filepath

    for attempt in range(1, max_retries + 1):
        try:
            print(f"Downloading {filename}, attempt {attempt}")
            with ftplib.FTP(ftp_host) as ftp:
                ftp.login(username, password)
                ftp.cwd(ftp_path)
                with open(local_filepath, 'wb') as file:
                    ftp.retrbinary(f'RETR {filename}', file.write)
            print(f"Downloaded {filename}")
            return local_filepath
        except ftplib.error_perm as e:
            # Handle session limit error specifically
            if '530' in str(e):
                print(f"FTP session limit reached, waiting before retrying {filename}...")
                time.sleep(10)  # Wait 10 seconds before retrying
            else:
                print(f"Permission error downloading {filename}: {e}")
                break
        except Exception as e:
            print(f"Error downloading {filename} (attempt {attempt}): {e}")
            time.sleep(5)  # Wait a few seconds before retry
    print(f"Failed to download {filename} after {max_retries} attempts.")
    return None

# --------------------------------------------------------------------------- # 

def _get_last_version_filename(filenames):
    versions = {int(f[-5:-3]): f for f in filenames}
    return versions[max(versions.keys())]

# --------------------------------------------------------------------------- # 

def _select_filename(filenames, only_last):
    if not only_last: return filenames
    return [_get_last_version_filename(filenames)]

# --------------------------------------------------------------------------- # 

def ftp_download_files_parallel(ftp_path, level, variant, cycle_numbers, half_orbits, output_dir, only_last=True, max_workers=4):
    """Download half orbit files in parallel from AVISO's FTP server."""
    ftpAVISO = 'ftp-access.aviso.altimetry.fr'
    ftp_details = (ftpAVISO, username, password)  # Use your FTP credentials here

    downloaded_files = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []

        for cycle in cycle_numbers:
            cycle_str = f'{cycle:03d}'
            cycle_dir = f'cycle_{cycle_str}'
            full_cycle_path = os.path.join(ftp_path, cycle_dir)

            for half_orbit in half_orbits:
                half_orbit_str = f'{half_orbit:03d}'
                pattern = f'SWOT_{level}_LR_SSH_{variant}_{cycle_str}_{half_orbit_str}'

                # Create a temporary FTP connection to list files
                try:
                    with ftplib.FTP(ftpAVISO) as ftp:
                        ftp.login(username, password)
                        ftp.cwd(full_cycle_path)
                        filenames = ftp.nlst(f'{pattern}_*')
                        if level == "L3":
                            only_last_flag = False
                        else:
                            only_last_flag = only_last
                        filenames = _select_filename(filenames, only_last_flag)
                except Exception as e:
                    print(f"No pass {half_orbit} in cycle {cycle}: {e}")
                    filenames = []

                for f in filenames:
                    futures.append(
                        executor.submit(_download_file_thread, ftp_details, full_cycle_path, f, output_dir, 3)
                    )

        for future in as_completed(futures):
            result = future.result()
            if result:
                downloaded_files.append(result)

    return downloaded_files

# --------------------------------------------------------------------------- # 

def _normalized_ds(ds, lon_min, lon_max):
    lon = ds.longitude.values
    lon[lon < lon_min] += 360
    lon[lon > lon_max] -= 360
    ds.longitude.values = lon
    return ds

# --------------------------------------------------------------------------- # 

def _subset_ds(file, variables, lon_range, lat_range, output_dir):
    print(f"Subset dataset: {file}")
    swot_ds = xr.open_dataset(file)
    swot_ds = swot_ds[variables]
    swot_ds.load()
    
    ds = _normalized_ds(swot_ds.copy(), -180, 180)

    mask = (
        (ds.longitude <= lon_range[1])
        & (ds.longitude >= lon_range[0])
        & (ds.latitude <= lat_range[1])
        & (ds.latitude >= lat_range[0])
    ).compute()
    
    swot_ds_area = swot_ds.where(mask, drop=True)

    if swot_ds_area.sizes['num_lines'] == 0:
        print(f'Dataset {file} not matching geographical area.')
        return None

    for var in list(swot_ds_area.keys()):
        swot_ds_area[var].encoding = {'zlib':True, 'complevel':5}

    filename = f"subset_{os.path.basename(urlparse(file).path)}"
    
    print(f"Store subset: {filename}")
    filepath = os.path.join(output_dir, filename)
    swot_ds_area.to_netcdf(filepath, mode='w')
        
    return filepath

# --------------------------------------------------------------------------- # 

def subset_files_parallel(filenames, variables, lon_range, lat_range, output_dir, max_workers=4):
    """Subset datasets in parallel with a given geographical area."""
    subsetted_files = []

    # Submit tasks to the executor
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_subset_ds, f, variables, lon_range, lat_range, output_dir): f for f in filenames}

        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                subsetted_files.append(result)

    return subsetted_files

# --------------------------------------------------------------------------- # 

def plot_datasets(filenames, variable, extent=None):
    cb_args = dict(
        add_colorbar=True,
        cbar_kwargs={"shrink": 0.3}
    )
    
    plot_kwargs = dict(
        x="longitude",
        y="latitude",
        cmap="Spectral_r",
        vmin=-0.2,
        vmax=0.2,
    )

    fig, ax = plt.subplots(figsize=(12, 8), subplot_kw=dict(projection=ccrs.PlateCarree()))
    if extent: ax.set_extent(extent)
    
    for filename in filenames:
        ds = xr.open_dataset(filename)
        ds[variable].plot.pcolormesh(
            ax=ax,
            **plot_kwargs,
            **cb_args)
        cb_args=dict(add_colorbar=False)
    
    ax.coastlines()
    ax.gridlines(draw_labels=True)









    