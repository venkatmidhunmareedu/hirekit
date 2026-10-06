import { type ReactNode, useEffect, useRef } from "react";

/**
 * A modal on the native dialog element: it traps focus, closes on Escape and returns
 * focus to the trigger (Design.md section 12). Render it only while open.
 */
export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    // jsdom has no showModal; the open attribute is the same state to the tests.
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
    return () => {
      if (typeof dialog.close === "function") dialog.close();
    };
  }, []);

  return (
    <dialog ref={ref} className="modal" aria-label={title} onCancel={onClose}>
      <h2>{title}</h2>
      {children}
    </dialog>
  );
}
