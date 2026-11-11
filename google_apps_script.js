/**
 * ==============================================================================
 * Prep404 BookScanner -> Google Drive Webhook Receiver
 * ==============================================================================
 * How to deploy this in 60 seconds (100% Free, No Credit Card, No GCP Project):
 *
 * 1. Open https://script.google.com in your browser (logged into your Google account).
 * 2. Click "+ New Project".
 * 3. Delete everything in the editor and PASTE this entire file.
 * 4. (Optional) If you want all scans in a specific folder, paste its folder ID below
 *    at ROOT_FOLDER_ID. Otherwise, it automatically creates a "BookScans" folder.
 * 5. Click "Deploy" (top right button) -> "New deployment".
 * 6. Click the gear icon next to "Select type" -> choose "Web app".
 * 7. Set:
 *    - Description: Book Scanner Drive Receiver
 *    - Execute as: Me (your email)
 *    - Who has access: Anyone (IMPORTANT: allows the scanner to upload files)
 * 8. Click "Deploy" -> authorize permissions with your Google account.
 * 9. Copy the generated "Web app URL" (looks like: https://script.google.com/macros/s/.../exec).
 * 10. Set that URL as an environment variable GDRIVE_WEBHOOK_URL on your cloud host
 *     (Render / Railway) or paste it in config.json!
 * ==============================================================================
 */

// OPTIONAL: Leave empty to save into a root "BookScans" folder,
// or paste a specific Google Drive Folder ID from its URL.
var ROOT_FOLDER_ID = "";

function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return ContentService.createTextOutput(JSON.stringify({
        success: false,
        error: "Missing post body"
      })).setMimeType(ContentService.MimeType.JSON);
    }

    var data = JSON.parse(e.postData.contents);
    var subject = (data.subject || "General").trim();
    var book = (data.book || "Book_Scans").trim();
    var filename = (data.filename || "scan.jpg").trim();
    var base64Data = data.image_base64;
    var mimeType = data.mime_type || "image/jpeg";

    if (!base64Data) {
      return ContentService.createTextOutput(JSON.stringify({
        success: false,
        error: "No image payload provided"
      })).setMimeType(ContentService.MimeType.JSON);
    }

    // 1. Resolve Root Destination Folder
    var parentFolder;
    if (ROOT_FOLDER_ID && ROOT_FOLDER_ID.length > 5) {
      parentFolder = DriveApp.getFolderById(ROOT_FOLDER_ID);
    } else {
      var rootIter = DriveApp.getRootFolder().getFoldersByName("BookScans");
      parentFolder = rootIter.hasNext() ? rootIter.next() : DriveApp.getRootFolder().createFolder("BookScans");
    }

    // 2. Resolve Subject Folder (e.g. "Physics 1st Paper")
    var subIter = parentFolder.getFoldersByName(subject);
    var subFolder = subIter.hasNext() ? subIter.next() : parentFolder.createFolder(subject);

    // 3. Resolve Book / Chapter Folder (e.g. "Chapter 4")
    var bookIter = subFolder.getFoldersByName(book);
    var bookFolder = bookIter.hasNext() ? bookIter.next() : subFolder.createFolder(book);

    // 4. Clean up any existing file with the same name (so retakes overwrite cleanly)
    var existingFiles = bookFolder.getFilesByName(filename);
    while (existingFiles.hasNext()) {
      existingFiles.next().setTrashed(true);
    }

    // 5. Decode base64 and write the file
    var decoded = Utilities.base64Decode(base64Data);
    var blob = Utilities.newBlob(decoded, mimeType, filename);
    var file = bookFolder.createFile(blob);

    return ContentService.createTextOutput(JSON.stringify({
      success: true,
      file_id: file.getId(),
      file_url: file.getUrl(),
      filename: filename,
      path: "BookScans/" + subject + "/" + book + "/" + filename
    })).setMimeType(ContentService.MimeType.JSON);

  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({
      success: false,
      error: error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

// Simple test ping
function doGet() {
  return ContentService.createTextOutput(JSON.stringify({
    status: "ok",
    service: "Prep404 BookScanner Google Drive Receiver"
  })).setMimeType(ContentService.MimeType.JSON);
}
