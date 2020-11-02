#!/usr/bin/env python
import click
import httpx
import os
import shutil
import tarfile
import tempfile
import time
import yaml
from jinja2 import Template
import rich.progress

with open("config.yaml") as f:
    config = yaml.load(f, Loader=yaml.FullLoader)


@click.command()
@click.argument("app")
@click.argument("version")
@click.option("--download-only", is_flag=True, help="download only")
@click.option("--force-download", is_flag=True, help="force download")
def cli(app, version, download_only, force_download):

    # Get paths and replace ~ with absolute path
    bin_dest = f"{config['bin_folder']}/{app}_{version}".replace("~", os.path.expanduser('~'))
    link_src = f"{config['link_folder']}/{app}".replace("~", os.path.expanduser('~'))

    # Check if app is already there
    if not os.path.exists(bin_dest) or force_download:

        # Download application to temp folder
        url_template = config["applications"][app]["url"]
        url = Template(url_template).render(version=version)
        click.echo(f"Downloading: {url}")

        with tempfile.NamedTemporaryFile() as dl_file:
            # click.echo(dl_file.name)
            with httpx.stream("GET", url) as resp:
                total = int(resp.headers["Content-Length"])

                with rich.progress.Progress(
                    "[progress.percentage]{task.percentage:>3.0f}%",
                    rich.progress.BarColumn(bar_width=None),
                    rich.progress.DownloadColumn(),
                    rich.progress.TransferSpeedColumn(),
                ) as progress:
                    download_task = progress.add_task("Download", total=total)
                    for chunk in resp.iter_bytes():
                        dl_file.write(chunk)
                        progress.update(
                            download_task, completed=resp.num_bytes_downloaded
                        )

            # TODO: check if downloaded file is ok/non-zero/binary/tar
            # TODO: check checksum if provided

            # Extract if it's tar
            if tarfile.is_tarfile(dl_file.name):
                with tempfile.TemporaryDirectory() as extract_dir:
                    # click.echo(extract_dir)
                    extract_bin = config["applications"][app]["extract_bin"]

                    tar = tarfile.open(dl_file.name)
                    tar.extract(extract_bin, extract_dir)
                    tar.close()

                    # override original downloaded file with extracted bin
                    shutil.copyfile(extract_dir + "/" + extract_bin, dl_file.name)

            # cp bin to bin_folder, prefix with version
            shutil.copyfile(dl_file.name, bin_dest)

            # chmod +x
            os.chmod(bin_dest, 0o755)

    # Creale symlink to app
    if os.path.islink(link_src):
        os.unlink(link_src)
    link_rel_dest = os.path.relpath(bin_dest, os.path.dirname(link_src))
    os.symlink(link_rel_dest, link_src)


if __name__ == "__main__":
    cli()
