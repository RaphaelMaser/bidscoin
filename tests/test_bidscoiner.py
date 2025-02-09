import json
from pathlib import Path
try:
    from bidscoin import bcoin, bidsmapper, bidscoiner
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parents[1]/'bidscoin'))      # This should work if bidscoin was not pip-installed
    import bcoin, bidsmapper, bidscoiner

bcoin.setup_logging()


def test_bidscoiner(raw_dicomdir, bids_dicomdir, bidsmap_dicomdir):
    if not bidsmap_dicomdir.is_file():
        bidsmapper.bidsmapper(raw_dicomdir, bids_dicomdir, bidsmap_dicomdir, bcoin.bidsmap_template, [], 'Doe^', '*', unzip='', noeditor=True, force=True)
        try:
            (bidsmap_dicomdir.parent/'bidsmapper.errors').unlink(missing_ok=True)
        except Exception:
            pass
    bidscoiner.bidscoiner(raw_dicomdir, bids_dicomdir)
    logs     = (bidsmap_dicomdir.parent/'bidscoiner.errors').read_text()
    sidecars = sorted((bids_dicomdir/'sub-Peter'/'ses-03Brain'/'extra_data').glob('*TestExtAtrributes*.json'))
    try:
        (bidsmap_dicomdir.parent/'bidscoiner.errors').unlink(missing_ok=True)
    except Exception:
        pass
    assert 'ERROR' not in logs
    # assert 'WARNING' not in logs
    # assert (bidsmap_dicomdir.parent/'bidscoiner.errors').stat().st_size == 0
    assert (bids_dicomdir/'sub-Archibald'/'ses-02CTHEADBRAINWOCONTRAST').is_dir()
    assert (bids_dicomdir/'sub-Peter'/'ses-01').is_dir()
    assert (bids_dicomdir/'sub-Peter'/'ses-04BrainMRA').is_dir()
    assert len(list(bids_dicomdir.rglob('*.nii*'))) > 3             # Exact number (10) is a bit arbitrary (depends on what dcm2niix can convert)
    assert sidecars[0].is_file()
    with sidecars[0].open('r') as json_fid:
        metadict = json.load(json_fid)
    assert metadict.get('ProtocolName')      == 'T/S/C RF FAST PILOT'
    assert metadict.get('SeriesDescription') == 'TestExtAtrributes'
    assert metadict.get('Comment')           == 'TestExtComment'

# def test_addmetadata(bids_dicomdir, bidsmap_dicomdir):
#     bidsmap, _ = bids.load_bidsmap(bidsmap_dicomdir)
#     bidscoiner.addmetadata(bids_dicomdir/'sub-something'/'ses-else', '*', '*')
