# tb-chatgpt-export-viewer

**Version:** 1.0.18  |  **Last updated:** 2026-11-16  |  **License:** MIT

A small Python utility that converts a ChatGPT data export into a **searchable, offline HTML conversation viewer**. It creates a separate HTML page for each conversation, restores available attachments, and generates a full-text search interface that can be opened directly from your file system.

This is an independent, unofficial utility and is not affiliated with or endorsed by OpenAI.

## Features

- Reads a ChatGPT data export **ZIP file** or an **already extracted directory**.
- Creates an `index.html` listing conversations, ordered by most recent update. It also records the generation time, program name/version, input ZIP metadata (when applicable), and an inventory of all extracted export files with links to restored `.dat` assets. The inventory panels retain their expanded/collapsed state and inner-list scroll position when navigating to an asset and back, or when reloading the page (where browser storage/history permits).
- Searches the full text of user and assistant messages, as well as conversation titles. With `--show-internal`, exported internal messages are searchable too.
- Shows the number of matching messages per conversation and all matching snippets in a scrollable area. Click a snippet to jump to its message.
- Works offline by loading `search_data.js` using an ordinary `<script>` tag—no web server, internet connection, external search service, or API key required.
- Creates individual conversation HTML pages with timestamps, date navigation, basic Markdown formatting (including tables), and local attachment links when source files are available.
- Attempts to restore exported file names from `library_files.json` and `conversation_asset_file_names.json`.
- Marks assistant-generated files and identifies files missing from the export.
- Optionally includes exported internal message records in both conversation pages and search using `--show-internal`.
- Checks actual HTML link attributes in generated `index.html` and `chats/*.html`, reporting missing targets without mistaking code examples for links. A warning does not by itself prove that an original export file is missing.
- Uses the Python standard library; no third-party packages required.

## Requirements

- Python **3.10 or newer**. Tested on **Windows with Python 3.13**; operation on macOS/Linux has not been verified.
- A modern browser such as Chrome, Edge, or Firefox.
- Enough free disk space for the uncompressed export, a temporary output directory, and attachments. Large exports may require several gigabytes.

## Usage

Download `tb_chatgpt_export_viewer.py` and run it from a terminal. The positional `input` argument is **optional**: when omitted, the program reads the already-extracted export directory `./chatgpt_export_work`. The default output directory is `./chatgpt_export_viewer` (`--out`). When a ZIP is given as `input`, `--work` specifies the extraction directory (default: `./chatgpt_export_work`); `--work` does **not** change the input directory when `input` is omitted. All relative paths are resolved against the **current working directory**, not the directory containing the script. Absolute paths are also supported.

### Using the default extracted export directory (input omitted)

If `./chatgpt_export_work` already contains an extracted export, you can omit `input` entirely. For example, from `D:\chatgpt_exported`:

```powershell
python C:\Python\tb-chatgpt-export-viewer\tb_chatgpt_export_viewer.py --show-internal
```

This reads `D:\chatgpt_exported\chatgpt_export_work` and writes `D:\chatgpt_exported\chatgpt_export_viewer`. If the default input directory does not exist, the program reports an error; it does not automatically locate or extract a ZIP.

### From an extracted export directory (explicit input)

```powershell
python tb_chatgpt_export_viewer.py "D:\chatgpt_exported\chatgpt_export_work" --out "D:\chatgpt_exported\chatgpt_export_viewer"
```

### From a ZIP file

```powershell
python tb_chatgpt_export_viewer.py "D:\chatgpt_export.zip" --out "D:\chatgpt_export_viewer" --work "D:\chatgpt_export_work"
```

### Show exported internal messages

```powershell
python tb_chatgpt_export_viewer.py "D:\chatgpt_exported\chatgpt_export_work" --out "D:\chatgpt_exported\chatgpt_export_viewer" --show-internal
```

### Other commands

```powershell
python tb_chatgpt_export_viewer.py --help
python tb_chatgpt_export_viewer.py --version
```

After conversion, open **`index.html`** in your browser. Expand **Export and generation information** to see when the viewer was generated, the program name/version, the input ZIP filename/modified time/size (for ZIP input), and the original files under the extracted export directory. Each exported `.dat` has a link to its restored `assets/` file when a corresponding copy exists. The inventory records the extracted files' original sizes and local modification times, not the generated HTML files' sizes. The inventory includes local source paths and filenames, so keep the viewer private.

**Note:** For ZIP input, the archive is first extracted into a new staging directory next to `--work` and checked for `conversations.json`. Only after successful extraction does the program replace the existing `--work` directory. If extraction fails, the existing directory is kept. If an old work directory cannot be renamed (for example because a file is in use), the program reports an error without deleting it. If replacement fails after the old directory has been moved aside, the program attempts to restore it and reports the backup location if rollback is blocked. After a successful replacement, an old backup that cannot be deleted is retained with a warning. **An existing `--work` directory is always replaced on a successful ZIP run; it is never merged with the new export.** The ZIP file must be outside `--work`.

The program replaces an existing output directory after generating the new viewer. Back up any files you manually added to that directory. Do not place the work directory inside the output directory, or vice versa.

## Output structure

```text
chatgpt_export_viewer/
  index.html          Conversation search plus viewer generation information and source-file inventory
  search_data.js      Full-text data from messages and titles
  chats/              One HTML file per conversation
  assets/             Available exported attachments
```

Keep the whole output folder together when copying or moving it. Local links are relative paths.

## Search behavior

- Search is **case-insensitive** and uses exact, contiguous text matching within each term, including Japanese. For example, searching for `警察署` matches `○○警察署`, but does **not** match `警察官`. There is no synonym, fuzzy, or morphological matching.
- Multiple terms separated by spaces must all appear **in the same message**, or all appear in the conversation title.
- The result count is the number of matching messages, not the number of word occurrences.
- Matching snippets link to the corresponding message on the conversation page.
- Search covers user/assistant messages and titles by default. If `--show-internal` is enabled, exported internal messages are also indexed. Attachment file contents and binary data are not indexed.
- Search runs automatically as you type; no Search button or Enter key is required. A short debounce avoids running a full scan after every keystroke. The search query and results are restored after browser Reload and Back/Forward navigation (using tab-local session storage with a history-state fallback).
- The browser loads the full search dataset into memory. Performance depends on the actual size of the text portion of your export, not the size of the ZIP archive. Very large text histories may cause slow startup or searches.

## Limitations

- ChatGPT's export format can change. Some message types, advanced formatting, citations, and embedded media may not render exactly as in ChatGPT.
- Some assistant-generated downloads and older attachments **are not included** in an export. The viewer cannot recreate missing file bytes.
- File-name collisions may be resolved with numbered names to prevent overwriting.
- Basic Markdown is supported, not a complete Markdown rendering engine.
- The generated search file includes potentially sensitive message text, even if it is not visibly displayed on the index page.
- Link checks cover local `href` and `src` paths in the generated HTML, not remote destinations or every possible JavaScript-created link.

## Privacy and security

**Do not upload your exported conversations, generated `index.html`, `search_data.js`, `chats/`, or `assets/` folder to a public GitHub repository.** These files can contain personal messages, documents, and other sensitive information.

This script performs local conversion only; it does not call network APIs or transmit your data. External links present in conversations can still open external websites if you click them. Like other offline exporters, it is best used with exports you trust.

Only publish the script, README, license, and other project-source files.

## License

MIT — see [LICENSE](LICENSE).

## Tests

The `tests/` directory contains automated checks for the developer/contributor, using small synthetic exports; it is **not needed for normal use**. To convert exports, only `tb_chatgpt_export_viewer.py` is required (Python standard library, no additional installation).

To run the tests, download the full repository and open a terminal in its **root directory**, the directory containing both `tb_chatgpt_export_viewer.py` and `tests/`. For example, on Windows PowerShell:

```powershell
cd C:\Python\tb-chatgpt-export-viewer
python -m unittest discover -s tests
```

A successful run finishes with `OK` and no `FAILED` or `ERROR` lines, for example:

```text
Ran 46 tests in 1.2s

OK
```

The exact test count and duration may vary with the version and computer. `__pycache__/` and `.pyc` files are Python caches, not test data; they can be deleted and should not be committed. The tests are regression/smoke checks, **not** a full guarantee that every ChatGPT export variant works.

## Maintenance

ChatGPT export structures are not guaranteed to remain unchanged. Check the *Last updated* date and open an issue if a newer export cannot be converted.

### Link conversion notes

The viewer turns HTTP(S) Markdown links into clickable hyperlinks, and resolves
exported `sandbox:/mnt/data/` links when the corresponding asset is available.
Other Markdown-looking fragments (such as regular expressions, legacy search
reference IDs, and unresolvable relative paths) remain as text rather than
becoming broken local hyperlinks.

### Unavailable attachments and audio clips

When an attachment reference exists but its file is not included in the export, the viewer retains a non-clickable placeholder. It shows the original filename when available, or a media/content type; if present, metadata such as the asset pointer, format, MIME type, or file ID is also displayed. An audio asset pointer alone does not mean the recorded audio is present in the export.

### Conversation branches

The viewer retains exported alternate conversation branches. It identifies the **Main** path by following `current_node` and `parent` links in `conversations.json`, and displays other paths as **Branch 1**, **Branch 2**, etc. Branches remain visible in the same page, with a navigation summary at the top of each chat. With `--show-internal`, thoughts and reasoning recap entries are placed before the assistant answer they lead to, separately for each branch (using exported parent links in both ancestor and descendant directions). When the divergence point is displayed, an alternate message links back to it. Older export formats without `current_node` retain the existing presentation without inferred branch labels.

### Generated file links

Sandbox-generated file links are shown in-place with the **original filename** as the clickable text, followed by the original descriptive Markdown label when different. If the file is not included in the export, the filename and label remain visible with `(not found in assets)` rather than a broken link.

### Console progress and counts

For ZIP input, the console reports when extraction starts and finishes; extracted directory input skips this step. During attachment pre-copy, progress is reported every 25 `.dat` files (and at completion).

For example, the following values are from one particular export, not fixed totals:

```text
[INFO] library_files.json: 556 filename mappings loaded
[INFO] conversation_asset_file_names.json: 254 attachment filename mappings loaded
[INFO] Export .dat files: 450; copied: 450 (library: 448, fallback: 2, raw: 0)
[INFO] Local links checked: 1151; broken: 0
```

- **`library_files.json: 556 filename mappings loaded`**: 556 file-ID-to-original-filename entries were loaded from `library_files.json`. This is a mapping count, **not** the number of physical files in the ZIP.
- **`conversation_asset_file_names.json: 254 attachment filename mappings loaded`**: 254 attachment-name entries were loaded from `conversation_asset_file_names.json`. Some IDs may also occur in the library mappings; the two counts should not be added to infer a file total.
- **`Export .dat files: 450`**: 450 eligible `.dat` source files were found in the extracted export for the pre-copy step.
- **`copied: 450`**: 450 file-ID records were registered by pre-copy. The current code skips writing an asset if the destination file already exists, so this count does not necessarily mean 450 newly written files.
- **`library: 448`**: 448 `.dat` inputs used filenames from `library_files.json`.
- **`fallback: 2`**: 2 `.dat` inputs had no usable library filename and used another available name source, such as `conversation_asset_file_names.json` or conversation attachment metadata.
- **`raw: 0`**: 0 `.dat` inputs lacked a usable original filename and therefore needed to retain a raw `.dat` filename during pre-copy. These three categories (`library`, `fallback`, `raw`) add up to the number of processed `.dat` files.

The following cleanup line is **optional**; it is printed only when redundant raw `.dat` copies were actually removed:

```text
[INFO] Removed 2 redundant raw .dat file(s) from assets
```

It counts **extra raw `.dat` copies removed after conversation HTML generation**, not the `raw` category in the pre-copy summary. Those extras could be created by a later attachment-processing step, so a nonzero removal count could previously appear even with `raw: 0`. Version 1.0.18 fixes a known `file-service://file-...` ID-parsing bug responsible for two such duplicate copies in a tested export. With that specific issue fixed, the cleanup line no longer appears when processing the affected export; cleanup remains as a safeguard for other cases.

- **`Local links checked: 1151`**: 1,151 *occurrences* of local `href` or `src` references in the generated `index.html` and `chats/*.html` were checked against the output files. This is **not** a unique file count; repeated references count repeatedly. External URLs and in-page `#...` anchors are excluded.
- **`broken: 0`**: no missing local targets were found among the checked links. This does **not** mean every original attachment was included in the ChatGPT export. If an attachment is unavailable, the viewer usually displays its reference without generating a clickable local link. The `broken` count reports distinct missing-link targets, rather than necessarily one count per occurrence.

### Assistant progress messages

Some assistant progress/status messages are present as ordinary `assistant` nodes on the export's `current_node` path even when the ChatGPT UI or PDF does not show them. They remain included as `Main` to preserve the exported record.
