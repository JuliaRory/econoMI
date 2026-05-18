

import h5py 

filename = r"data/S001/record.hdf5"
with h5py.File(filename, "r") as h5f:
    print(h5f.keys())
    print(h5f["responses"].keys())
    print(h5f["stimuli"].keys())
    print(h5f["stimuli/messages"][()])