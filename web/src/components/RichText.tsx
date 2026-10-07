import { Markdown as MarkdownExtension } from "@tiptap/markdown";
import { Plugin } from "@tiptap/pm/state";
import { EditorContent, Extension, useEditor, type Editor } from "@tiptap/react";
import { StarterKit } from "@tiptap/starter-kit";
import { Bold, Heading2, Italic, List, ListOrdered } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Plain-text paste (no HTML flavour on the clipboard) is read as markdown, so "- " and "## " become real blocks. */
const PasteMarkdown = Extension.create({
  name: "pasteMarkdown",
  addProseMirrorPlugins() {
    const editor = this.editor;
    return [
      new Plugin({
        props: {
          handlePaste: (_view, event) => {
            const data = event.clipboardData;
            const text = data?.getData("text/plain") ?? "";
            if (text === "" || (data?.getData("text/html") ?? "") !== "") return false;
            editor.commands.insertContent(text, { contentType: "markdown" });
            return true;
          },
        },
      }),
    ];
  },
});

// No links, images or raw HTML: a job description needs none, and fewer node types means less to render.
function extensions(withPaste: boolean) {
  return [
    StarterKit.configure({ link: false, underline: false, codeBlock: false, code: false }),
    MarkdownExtension,
    ...(withPaste ? [PasteMarkdown] : []),
  ];
}

function markdownOf(editor: Editor): string {
  return editor.isEmpty ? "" : editor.getMarkdown().trim();
}

interface ToolbarItem {
  label: string;
  icon: typeof Bold;
  active: (e: Editor) => boolean;
  run: (e: Editor) => void;
}

const ITEMS: ToolbarItem[] = [
  {
    label: "Bold",
    icon: Bold,
    active: (e) => e.isActive("bold"),
    run: (e) => e.chain().focus().toggleBold().run(),
  },
  {
    label: "Italic",
    icon: Italic,
    active: (e) => e.isActive("italic"),
    run: (e) => e.chain().focus().toggleItalic().run(),
  },
  {
    label: "Heading",
    icon: Heading2,
    active: (e) => e.isActive("heading", { level: 2 }),
    run: (e) => e.chain().focus().toggleHeading({ level: 2 }).run(),
  },
  {
    label: "Bulleted list",
    icon: List,
    active: (e) => e.isActive("bulletList"),
    run: (e) => e.chain().focus().toggleBulletList().run(),
  },
  {
    label: "Numbered list",
    icon: ListOrdered,
    active: (e) => e.isActive("orderedList"),
    run: (e) => e.chain().focus().toggleOrderedList().run(),
  },
];

/** Markdown in, markdown out. `id` goes on the editable area so a `<Label htmlFor>` points at it. */
export function MarkdownEditor({
  id,
  label,
  value,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (markdown: string) => void;
}) {
  const editor = useEditor({
    extensions: extensions(true),
    shouldRerenderOnTransaction: true,
    content: value,
    contentType: "markdown",
    editorProps: {
      attributes: {
        id,
        role: "textbox",
        "aria-multiline": "true",
        "aria-label": label,
        class: "rich-text min-h-48 px-3 py-2 outline-none",
      },
    },
    onUpdate: ({ editor: e }) => {
      onChange(markdownOf(e));
    },
  });

  return (
    <div className="rounded-md border bg-background focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50">
      <div role="toolbar" aria-label="Formatting" className="flex gap-1 border-b p-1">
        {ITEMS.map(({ label: name, icon: Icon, active, run }) => {
          const on = active(editor);
          return (
            <Button
              key={name}
              type="button"
              variant={on ? "secondary" : "ghost"}
              size="icon-sm"
              aria-label={name}
              aria-pressed={on}
              onClick={() => {
                run(editor);
              }}
            >
              <Icon aria-hidden />
            </Button>
          );
        })}
      </div>
      <EditorContent editor={editor} className="max-h-[45svh] overflow-y-auto" />
    </div>
  );
}

/** Read-only markdown. Unknown markup (raw HTML, links, images) is dropped by the schema, never rendered. */
export function Markdown({ value, className }: { value: string; className?: string }) {
  const editor = useEditor(
    {
      extensions: extensions(false),
      content: value,
      contentType: "markdown",
      editable: false,
      editorProps: { attributes: { class: cn("rich-text text-sm", className) } },
    },
    [value],
  );
  return <EditorContent editor={editor} />;
}
