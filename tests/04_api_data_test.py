from brkraw_legacy.api.data import Study


def test_data_init(dataset):
    """The high-level Study container builds from each study and lists its scans."""
    for pvobj in dataset.values():
        studyobj = Study(pvobj.path)
        assert studyobj.avail, 'Study should enumerate available scans'
