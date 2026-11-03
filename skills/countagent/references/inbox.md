# Phone capture (inbox)

The inbox is a plain text file, one entry per line, that the phone appends to and the agent empties. It needs no app and no server: any sync service that keeps a text file in sync works (iCloud Drive, Dropbox, Google Drive, Syncthing).

Set it with `--inbox <path>` at setup, or later via `"inbox"` in `config.json`. `~` is allowed.

## iPhone: Shortcuts + Siri (recommended)

1. In the **Shortcuts** app, make a new shortcut named e.g. **Log it**.
2. Action **Ask for Input** (Text). Prompt: "What did you spend?"
3. Action **Format Date** → current date, ISO 8601, with time. Optional, but it keeps late-night entries on the right day.
4. Action **Text**: `<Formatted Date> <Provided Input>`.
5. Action **Append to Text File**. File: `inbox.txt` in the Shortcuts iCloud folder. Turn on *Make New Line*.

"Hey Siri, Log it" → "lunch 12" is then a single line in the file.

The Shortcuts iCloud folder on a Mac is:
`~/Library/Mobile Documents/iCloud~is~workflow~my~workflows/Documents/inbox.txt`

## Android

Any app that appends a line to a synced text file works. For example, **Tasker** or **Automate** with a voice-input step, then "Write File (append)" into a Dropbox or Drive folder that is synced to the computer.

## Anywhere else

A notes app that syncs a plain `.txt`, or even a Telegram-to-file bot. The only contract: one entry per line; lines starting with `#` are ignored.

## Processing rules (for the agent)

1. **Read** the file. Ignore blank lines and lines starting with `#`.
2. **Exact dedup.** A line that appears verbatim in `inbox_archive.txt` was already processed; skip it. Sync services sometimes resurrect old lines.
3. **Same-day duplicate.** If a line matches an existing ledger entry with the same day, same amount and same meaning, record it once and ask. Different wording ("lunch 12" and "noodles 12") on the same day counts as the same meaning if it is plausibly the same meal.
4. **Interpret** each line (SKILL.md, section 2). Use the leading timestamp as the logging time.
5. **Append** to `ledger.csv`.
6. **Archive** the processed raw lines to `inbox_archive.txt`, byte for byte (keep trailing spaces, so step 2 keeps working).
7. **Leave in the inbox** only the lines you could not interpret, and ask about them. Otherwise empty the file. Overwrite it; don't delete it, or the phone shortcut may lose its target.
8. **Re-read the inbox just before you rewrite it.** A new line may have arrived while you worked; don't wipe it.
9. **Report:** how many were recorded, one line each, anything skipped or questioned, and the current period's status.

### Fixed costs during processing

After recording the inbox, check `profile.md` for **auto** recurring charges whose charge day has passed in the current period and that aren't in the ledger yet. Add them with note `fixed;auto-added`, list them in the report, and never add **manual** ones.
