/**
 * ==============================================================================
 * Prep404 BookScanner -> Google Drive Webhook Receiver (Read + Write)
 * ==============================================================================
 * To update an existing deployment WITHOUT changing its URL:
 * 1. Open your project at https://script.google.com
 * 2. Replace everything with this updated code and Save (Ctrl+S).
 * 3. Click "Deploy" (top right) -> "Manage deployments".
 * 4. Click the Edit (pencil) icon -> Version: "New version" -> Click "Deploy".
 * ==============================================================================
 */

// OPTIONAL: Leave empty to save into a root "BookScans" folder,
// or paste a specific Google Drive Folder ID from its URL.
var ROOT_FOLDER_ID = "";

function resolveParentFolder(customFolderId) {
  var targetFolderId = (customFolderId || ROOT_FOLDER_ID || "").trim();
  if (targetFolderId && targetFolderId.length > 5) {
    try {
      return DriveApp.getFolderById(targetFolderId);
    } catch (err) {}
  }
  var rootIter = DriveApp.getRootFolder().getFoldersByName("BookScans");
  return rootIter.hasNext() ? rootIter.next() : DriveApp.getRootFolder().createFolder("BookScans");
}

function jsonOut(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return jsonOut({ success: false, error: "Missing post body" });
    }

    var data = JSON.parse(e.postData.contents);
    var subject = (data.subject || "General").trim();
    var book = (data.book || "Book_Scans").trim();
    var filename = (data.filename || "scan.jpg").trim();
    var base64Data = data.image_base64;
    var mimeType = data.mime_type || "image/jpeg";

    if (!base64Data) {
      return jsonOut({ success: false, error: "No image payload provided" });
    }

    var parentFolder = resolveParentFolder(data.folder_id);

    // Resolve Subject Folder
    var subIter = parentFolder.getFoldersByName(subject);
    var subFolder = subIter.hasNext() ? subIter.next() : parentFolder.createFolder(subject);

    // Resolve Book / Chapter Folder
    var bookIter = subFolder.getFoldersByName(book);
    var bookFolder = bookIter.hasNext() ? bookIter.next() : subFolder.createFolder(book);

    // Overwrite existing file with the same name cleanly
    var existingFiles = bookFolder.getFilesByName(filename);
    while (existingFiles.hasNext()) {
      existingFiles.next().setTrashed(true);
    }

    var decoded = Utilities.base64Decode(base64Data);
    var blob = Utilities.newBlob(decoded, mimeType, filename);
    var file = bookFolder.createFile(blob);

    return jsonOut({
      success: true,
      file_id: file.getId(),
      file_url: file.getUrl(),
      filename: filename,
      path: "BookScans/" + subject + "/" + book + "/" + filename
    });
  } catch (error) {
    return jsonOut({ success: false, error: error.toString() });
  }
}

function doGet(e) {
  try {
    var params = (e && e.parameter) ? e.parameter : {};
    var action = params.action || "";

    // 1. List Subject -> Book folder tree from Google Drive
    if (action === "tree") {
      var parentFolder = resolveParentFolder(params.folder_id);
      var tree = {};
      var subFolders = parentFolder.getFolders();

      while (subFolders.hasNext()) {
        var sub = subFolders.next();
        var subName = sub.getName();
        var books = [];
        var bkFolders = sub.getFolders();

        while (bkFolders.hasNext()) {
          var bk = bkFolders.next();
          var files = bk.getFiles();
          var count = 0;
          var maxPage = 0;
          while (files.hasNext()) {
            var f = files.next();
            var m = f.getName().match(/^page_(\d+)\.jpg$/i);
            if (m) {
              count++;
              var pNum = parseInt(m[1], 10);
              if (pNum > maxPage) maxPage = pNum;
            }
          }
          books.push({
            name: bk.getName(),
            pages: count,
            next_page: maxPage + 1
          });
        }

        // Sort books alphabetically
        books.sort(function(a, b) { return a.name.localeCompare(b.name); });
        tree[subName] = books;
      }

      return jsonOut({ success: true, tree: tree });
    }

    // 2. List scanned pages inside a specific Subject / Book
    if (action === "pages") {
      var subject = (params.subject || "General").trim();
      var book = (params.book || "Book_Scans").trim();
      var parentFolder = resolveParentFolder(params.folder_id);

      var subIter = parentFolder.getFoldersByName(subject);
      if (!subIter.hasNext()) {
        return jsonOut({ success: true, subject: subject, book: book, pages: [], next_page: 1, total: 0 });
      }
      var subFolder = subIter.next();

      var bookIter = subFolder.getFoldersByName(book);
      if (!bookIter.hasNext()) {
        return jsonOut({ success: true, subject: subject, book: book, pages: [], next_page: 1, total: 0 });
      }
      var bookFolder = bookIter.next();

      var pages = [];
      var maxPage = 0;
      var files = bookFolder.getFiles();
      while (files.hasNext()) {
        var f = files.next();
        var m = f.getName().match(/^page_(\d+)\.jpg$/i);
        if (m) {
          var pNum = parseInt(m[1], 10);
          if (pNum > maxPage) maxPage = pNum;
          pages.push({
            page_number: pNum,
            filename: f.getName(),
            file_id: f.getId()
          });
        }
      }

      pages.sort(function(a, b) { return a.page_number - b.page_number; });

      return jsonOut({
        success: true,
        subject: subject,
        book: book,
        pages: pages,
        next_page: maxPage + 1,
        total: pages.length
      });
    }

    // 3. Return base64 image for thumbnail preview proxy
    if (action === "image_b64" && params.id) {
      var file = DriveApp.getFileById(params.id);
      var blob = file.getBlob();
      return jsonOut({
        success: true,
        mime_type: blob.getContentType(),
        base64: Utilities.base64Encode(blob.getBytes())
      });
    }

    // Default ping
    return jsonOut({
      status: "ok",
      service: "Prep404 BookScanner Google Drive Receiver"
    });
  } catch (error) {
    return jsonOut({ success: false, error: error.toString() });
  }
}
