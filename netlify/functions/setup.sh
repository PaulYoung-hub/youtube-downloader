#!/bin/bash
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o "/opt/build/repo/netlify/functions/yt-dlp"
chmod +x "/opt/build/repo/netlify/functions/yt-dlp"
