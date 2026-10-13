// Copy to config.js (gitignored) and set the HTTP API invoke URL, without a trailing slash.
// API Gateway console -> APIs -> resumerank-api -> Stages -> $default -> Invoke URL
window.RESUMERANK_CONFIG = {
  apiBaseUrl: "https://<api-id>.execute-api.ap-south-1.amazonaws.com",
};
