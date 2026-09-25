# Software and measurement correspondence

All primary native, Python and numerical results evaluate the fixed BRiDCT 0.2.0-dev.7 implementation distributed here. The native Mac library and the compiled Python extension use identical ARM object code. Two fresh-process sessions per comparator family use 21 randomized blocks with a 30 ms target. Ratios are formed within the same session and contract; no times from distinct campaigns are pooled.

The main memory-intervention figure and the inverse16 parent/candidate table are explicitly labelled development ablations. They explain the design and retain their original matched observations. The Windows workstation screen also evaluates dev.7, under its own exploratory protocol. Earlier Ubuntu returns do not count as a final-release evaluation.

The separate [`bridct-measurements.zip`](https://github.com/antmoev/bridct/releases) release asset contains recorded CSV timings, numerical checks and technical metadata. Its README maps files to figures and tables. CSV values are unchanged. Exported JSON omits personal home paths, host identity fields and process listings; original and exported hashes are recorded.

Platform launchers create new measurements on the recipient's machine. OpenCV, SciPy, DUCC and pyFFTW are compared through Python; Ooura is compared separately in C. The optional native macOS helper documents the vDSP/FFTW/codec campaign. Benchmarking another machine is distinct from reanalyzing the recorded observations.

Paper and supplement: https://arxiv.org/abs/2609.28519.
