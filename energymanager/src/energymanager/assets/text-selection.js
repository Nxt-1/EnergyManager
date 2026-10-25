export function hasTextSelection(root) {
  const document = root.ownerDocument || root;
  const selections = [root.getSelection?.(), document.getSelection?.()].filter(Boolean);
  return selections.some(selection => {
    if (selection.isCollapsed) return false;
    if (root.contains(selection.anchorNode) || root.contains(selection.focusNode)) return true;
    // Document-wide selection may expose only the shadow host as its boundary.
    return !!root.host && Array.from({length: selection.rangeCount}, (_, index) =>
      selection.getRangeAt(index)).some(range => range.intersectsNode(root.host));
  });
}

export function clearTextSelection(root) {
  const document = root.ownerDocument || root;
  for (const selection of [root.getSelection?.(), document.getSelection?.()])
    selection?.removeAllRanges();
}
