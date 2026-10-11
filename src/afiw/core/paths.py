from dataclasses import dataclass
from pathlib import Path
from .types import RunSpec

@dataclass(frozen = True)
class AFIWPaths:
    root   : str | Path
    run_cfg: RunSpec

    @property
    def station(self):
        return Path(self.root).expanduser().resolve()/self.run_cfg.region.name.lower()

    @property
    def catalog(self):
        return self.station/'catalog'

    @property
    def downloads(self):
        return self.station/'raw'

    @property
    def processed(self):
        return self.station/'processed'

    @property
    def products(self):
        return self.station/'products'

    @property
    def bulletins(self):
        return self.station/'bulletins'

    @property
    def logs(self):
        return Path.home() / 'afiw_data' / self.run_cfg.region.name.lower() / 'logs'

    def pair(self, pair_id):
        if not pair_id or any(c not in '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_' for c in pair_id):
            raise ValueError('Unsafe pair ID')
        return self.products/pair_id

    def ensure(self):
        for p in [self.catalog, self.downloads, self.processed, self.products, self.bulletins]:
            p.mkdir(parents = True, exist_ok = True)
        return self
