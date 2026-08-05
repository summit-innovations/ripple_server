# Ripple Server Project

This repository contains all the files related to the server-end daemons for the Ripple Glasses project. This server will be used for testing and experimentation.
As of now, there are two primary functions within the server: realtime uploads and training uploads. The realtime uploads are for presentation purposes and should simulate what the actual glasses will do.
The training uploads help refine and train the model. The endpoint code is found within `audio-uploader/main.py`.
The raw audio files are found in `audio-uploader/realtime-uploads/` or `audio-uploader/training-uploads/`,
the audio environment files are in `environment-uploader/realtime-uploads/` or `environment-uploader/trainig-uploads/`. 
The model is found in `environment-classifier/` and mostly maintained by Spencer Goff.  

## Changelog

- 7/27/2026: Configured git hub repository and README. I will be adding the current functions we are using to read and process the audio uploads to this repository today as well. 
- 7/27/2026: Moved `audio-upload/` and `environment-uploads/` folders to the repo. `audio-uploads/` contains the rudimentary functions that interact with the API, pulling from new uploads, and feed them to the model. The model hasn't been added yet, so it simply pulls from the API and adds the uploaded files to the `environment-uploads/` folder. `environment-uploads/` contains the files we've used to train and work with the model. They should be ignored using gitignore. 
- 7/27/2026: Actually, `environment-uploader/` likely takes the uploaded files from `audio-uploader/` and then scene classifies them. They are two separate functions. 
- 8/5/2026: Added endpoints for `realtime-uploads/` and `training-uploads/`. This will allow us to separate tasks
