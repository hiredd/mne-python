"""
=====================================
Time-frequency beamforming using LCMV
=====================================

Compute LCMV source power in a grid of time-frequency windows and display
results.

The original reference is:
Dalal et al. Five-dimensional neuroimaging: Localization of the time-frequency
dynamics of cortical activity. NeuroImage (2008) vol. 40 (4) pp. 1686-1700
"""

# Author: Roman Goj <roman.goj@gmail.com>
#
# License: BSD (3-clause)

print __doc__

import mne
from mne import compute_covariance
from mne.fiff import Raw
from mne.datasets import sample
from mne.event import make_fixed_length_events
from mne.beamformer import tf_lcmv
from mne.viz import plot_source_spectrogram


data_path = sample.data_path()
raw_fname = data_path + '/MEG/sample/sample_audvis_raw.fif'
noise_fname = data_path + '/MEG/sample/ernoise_raw.fif'
event_fname = data_path + '/MEG/sample/sample_audvis_raw-eve.fif'
fname_fwd = data_path + '/MEG/sample/sample_audvis-meg-eeg-oct-6-fwd.fif'
subjects_dir = data_path + '/subjects'
label_name = 'Aud-lh'
fname_label = data_path + '/MEG/sample/labels/%s.label' % label_name

###############################################################################
# Read raw data, preload to allow filtering
raw = Raw(raw_fname, preload=True)
raw.info['bads'] = ['MEG 2443']  # 1 bad MEG channel

# Set picks
picks = mne.fiff.pick_types(raw.info, meg=True, eeg=False, eog=False,
                            stim=False, exclude='bads')

# Read epochs without preloading to access the underlying raw object for
# filtering later in tf_lcmv
event_id, tmin, tmax = 1, -0.2, 0.5
reject = dict(grad=4000e-13, mag=4e-12)
events = mne.read_events(event_fname)
epochs = mne.Epochs(raw, events, event_id, tmin, tmax, proj=True,
                    picks=picks, baseline=(None, 0), preload=False,
                    reject=reject)

# Read empty room noise, preload to allow filtering
raw_noise = Raw(noise_fname, preload=True)
raw_noise.info['bads'] = ['MEG 2443']  # 1 bad MEG channel

# Create artificial events for empty room noise data which will later be used
# to create epochs from filtered data
events_noise = make_fixed_length_events(raw_noise, event_id, duration=1.)
# reject bad noise epochs based on unfiltered data
epochs_noise = mne.Epochs(raw_noise, events_noise, event_id, tmin, tmax,
                          proj=True, picks=picks, baseline=(None, 0),
                          preload=True, reject=reject)
# then make sure the number of noise epochs is the same as data epochs
epochs_noise = epochs_noise[:len(epochs.events)]

# Read forward operator
forward = mne.read_forward_solution(fname_fwd, surf_ori=True)

# Read label
label = mne.read_label(fname_label)

###############################################################################
# Time-frequency beamforming based on LCMV

# Setting frequency bins as in Dalal et al. 2008 (high gamma was subdivided)
freq_bins = [(4, 12), (12, 30), (30, 55), (65, 299)]  # Hz
win_lengths = [0.2, 0.2, 0.2, 0.2]  # s

# Setting time step and CSD regularization parameter
tstep = 0.2
reg = 0.1

# Calculating covariance from empty room noise. To use baseline data as noise
# substitute raw for raw_noise
noise_covs = []

for (l_freq, h_freq) in freq_bins:
    raw_band = raw_noise.copy()
    raw_band.filter(l_freq, h_freq, picks=epochs.picks, method='iir', n_jobs=1)
    epochs_band = mne.Epochs(raw_band, epochs_noise.events, event_id,
                             tmin=tmin, tmax=tmax, picks=epochs.picks,
                             proj=True)
    noise_cov = compute_covariance(epochs_band)
    noise_cov = mne.cov.regularize(noise_cov, epochs_band.info, mag=reg,
                                   grad=reg, eeg=reg, proj=True)
    noise_covs.append(noise_cov)
    del raw_band  # to save memory

# Computing LCMV solutions for time-frequency windows in a label in source
# space for faster computation, use label=None for full solution
stcs = tf_lcmv(epochs, forward, noise_covs, tmin, tmax, tstep, win_lengths,
               freq_bins=freq_bins, reg=reg, label=label)

# Plotting source spectrogram for source with maximum activity
plot_source_spectrogram(stcs, freq_bins, source_index=None)
