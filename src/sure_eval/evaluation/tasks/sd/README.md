# SD Evaluation

Speaker diarization uses the generic `scoring/meeteval` node and reports DER.

The default pipeline is `sd.any.der.meeteval_v1`; its route id is
`sd.der.meeteval` with `collar=0.25`. Reference and
hypothesis files are passed directly to `meeteval.io.load`; use a MeetEval
supported annotation format such as RTTM for DER.

The EAR-1 route `sd.any.der.conversion_sd_ear1_submission_v1.ear1_scorer_v1`
uses `conversion/sd__ear1_submission` and `scoring/ear1_scorer`. Inputs are
the submission ZIP (`hyp`), reference RTTM file or a directory containing
`reference.rttm` (`ref`) and organizer
`sessions.json` (`sessions`). It is not the default route.
