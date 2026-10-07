// Dump the operator prompt from the dsh-purge encrypted slot (read-only introspection).
import { openSlot } from "file:///C:/Users/Administrator/.dsh/profiles/web/node_modules/dsh-purge/lib/table-read.js";
const text = openSlot();
process.stdout.write(text);
