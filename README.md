# Ripple Server Project

This repository contains all the files related to the server-end daemons for the Ripple Glasses project. This server will be used for testing and experimentation. 

## Changelog

- 7/27/2026: Configured git hub repository and README. I will be adding the current functions we are using to read and process the audio uploads to this repository today as well. 
- 7/27/2026: Moved `audio-upload/` and `environment-uploads/` folders to the repo. `audio-uploads/` contains the rudimentary functions that interact with the API, pulling from new uploads, and feed them to the model. The model hasn't been added yet, so it simply pulls from the API and adds the uploaded files to the `environment-uploads/` folder. `environment-uploads/` contains the files we've used to train and work with the model. They should be ignored using gitignore. 
- 7/27/2026: Actually, `environment-uploader/` likely takes the uploaded files from `audio-uploader/` and then scene classifies them. They are two separate functions. 

