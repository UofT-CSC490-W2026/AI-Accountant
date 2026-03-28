import type { ClarificationItem } from "../api/types";

type ClarificationListProps = {
  items: ClarificationItem[];
  selectedId: string | null;
  onSelect: (item: ClarificationItem) => void;
};

export function ClarificationList({
  items,
  selectedId,
  onSelect,
}: ClarificationListProps) {
  return (
    <div className="clarification-list">
      {items.map((item) => (
        <button
          key={item.clarification_id}
          className={item.clarification_id === selectedId ? "list-card list-card-active" : "list-card"}
          onClick={() => onSelect(item)}
        >
          <span className="list-card-header">
            <span className="list-card-title">{item.source_text}</span>
            <span className="list-card-status">Pending</span>
          </span>
          <span className="list-card-meta">Confidence {item.confidence.overall.toFixed(2)}</span>
          <span className="list-card-copy">{item.explanation}</span>
        </button>
      ))}
    </div>
  );
}
