"""R2 (approved 2026-10-20): web lookups may only bring in pages from manufacturer (OEM) sites.

The allowlist is a plain table of maker web domains. A result is allowed when its host is (a subdomain of) any listed
maker domain. When the picked manuals name a maker that has its own entry, that maker's domains are listed first but any
maker domain is allowed (a Dometic-made part on a Lippert unit is documented on dometic.com).
"""
from urllib.parse import urlparse

OEM_DOMAINS = {
    "lippert": ("lci1.com", "lippert.com", "lippertcomponents.com", "lci-support-doc.s3.amazonaws.com"),
    "dometic": ("dometic.com",),
    "furrion": ("furrion.com",),
    "thetford": ("thetford.com",),
    "norcold": ("norcold.com", "thetford.com"),
    "suburban": ("airxcel.com", "suburbanrv.com"),
    "airxcel": ("airxcel.com",),
    "atwood": ("dometic.com", "airxcel.com"),
    "coleman-mach": ("airxcel.com", "rvcomfort.com"),
    "girard": ("girardrv.com",),
    "bal": ("norcoindustries.com", "balrv.com", "balrvproducts.com"),
    "truma": ("truma.com", "trumaservice.com"),
    "power gear": ("lci1.com", "lippert.com"),
    "kwikee": ("lci1.com", "lippert.com"),
    "hwh": ("hwh.com",),
    "renogy": ("renogy.com",),
    "victron": ("victronenergy.com",),
    "maxxair": ("maxxair.com",),
    "progressive dynamics": ("progressivedyn.com",),
    "xantrex": ("xantrex.com",),
    "onan": ("cummins.com",),
    "carefree": ("carefreeofcolorado.com",),
    "shurflo": ("shurflo.com", "pentair.com"),
    "valterra": ("valterra.com",),
    "remco": ("remcoindustries.com",),
    "wfco": ("wfcoelectronics.com",),
    "happijac": ("happijac.com",),
    "thule": ("thule.com",),
    "curt": ("curtmfg.com",),
}


def _host(url: str) -> str:
    try:
        return (urlparse(url or "").hostname or "").lower()
    except Exception:
        return ""


def allowed(url: str, brands=()) -> bool:
    host = _host(url)
    if not host:
        return False
    for doms in OEM_DOMAINS.values():
        for d in doms:
            if host == d or host.endswith("." + d):
                return True
    return False
