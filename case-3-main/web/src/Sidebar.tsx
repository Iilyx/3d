/** Liber left rail — New · Pinned · Folders · Recent · Settings (Codex-style). */

import { useMemo, useState } from "react";
import { useConfirm } from "./ConfirmModal";
import {
  IconChevron,
  IconFolder,
  IconLiberMark,
  IconPanelLeft,
  IconPin,
  IconPlus,
  IconSettings,
} from "./icons";
import {
  historyInFolder,
  type HistoryFolder,
  type HistoryItem,
} from "./domain/reportHistory";

export type { HistoryItem, HistoryFolder };

type Props = {
  collapsed: boolean;
  onToggle: () => void;
  healthReady: boolean;
  healthLabel: string;
  healthHint: string;
  /** Live Image API chip (ok / down) — Quiet Mono. */
  imageChipLabel?: string;
  imageChipOk?: boolean;
  imageChipHint?: string;
  history: HistoryItem[];
  folders: HistoryFolder[];
  onNew: () => void;
  onOpenHistory: (item: HistoryItem) => void;
  onTogglePin: (runId: string) => void;
  onMoveToFolder: (runId: string, folderId: string | null) => void;
  onCreateFolder: (name: string) => void;
  onRenameFolder: (id: string, name: string) => void;
  onDeleteFolder: (id: string) => void;
  onSettings: () => void;
  busy?: boolean;
};

function formatMeta(savedAt: number): string {
  return new Date(savedAt).toLocaleString("ru-RU", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function HistoryRow({
  item,
  folders,
  onOpen,
  onTogglePin,
  onMoveToFolder,
  busy,
}: {
  item: HistoryItem;
  folders: HistoryFolder[];
  onOpen: () => void;
  onTogglePin: () => void;
  onMoveToFolder: (folderId: string | null) => void;
  busy: boolean;
}) {
  const [menu, setMenu] = useState(false);
  return (
    <li className={`liber-hist-row${item.pinned ? " is-pinned" : ""}`}>
      <button
        type="button"
        className="liber-sidebar-history-item"
        onClick={onOpen}
        title={item.title}
        disabled={busy}
      >
        {item.pinned ? (
          <IconPin size={12} className="liber-hist-pin-mark" />
        ) : null}
        <span className="liber-sidebar-history-title">{item.title}</span>
        <span className="liber-sidebar-history-meta">
          {formatMeta(item.savedAt)}
        </span>
      </button>
      <div className="liber-hist-actions">
        <button
          type="button"
          className={`liber-hist-act${item.pinned ? " is-on" : ""}`}
          title={item.pinned ? "Открепить" : "Закрепить"}
          aria-label={item.pinned ? "Открепить" : "Закрепить"}
          disabled={busy}
          onClick={(e) => {
            e.stopPropagation();
            onTogglePin();
          }}
        >
          <IconPin size={14} />
        </button>
        <div className="liber-hist-menu-wrap">
          <button
            type="button"
            className={`liber-hist-act${menu ? " is-on" : ""}`}
            title="В папку"
            aria-label="Переместить в папку"
            aria-expanded={menu}
            disabled={busy}
            onClick={(e) => {
              e.stopPropagation();
              setMenu((v) => !v);
            }}
          >
            <IconFolder size={14} />
          </button>
          {menu ? (
            <div className="liber-hist-menu" role="menu">
              <button
                type="button"
                role="menuitem"
                className={!item.folderId ? "is-active" : undefined}
                onClick={() => {
                  onMoveToFolder(null);
                  setMenu(false);
                }}
              >
                Без папки
              </button>
              {folders.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  role="menuitem"
                  className={item.folderId === f.id ? "is-active" : undefined}
                  onClick={() => {
                    onMoveToFolder(f.id);
                    setMenu(false);
                  }}
                >
                  {f.name}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </li>
  );
}

function FolderBlock({
  title,
  items,
  folders,
  defaultOpen = false,
  folderId: _folderId,
  onOpenHistory,
  onTogglePin,
  onMoveToFolder,
  onRename,
  onDelete,
  busy,
}: {
  title: string;
  items: HistoryItem[];
  folders: HistoryFolder[];
  defaultOpen?: boolean;
  folderId: string;
  onOpenHistory: (item: HistoryItem) => void;
  onTogglePin: (runId: string) => void;
  onMoveToFolder: (runId: string, folderId: string | null) => void;
  onRename: (name: string) => void;
  onDelete: () => void;
  busy: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const [renaming, setRenaming] = useState(false);
  const [nameDraft, setNameDraft] = useState(title);
  const confirm = useConfirm();

  return (
    <section className={`liber-hist-group${open ? " is-open" : ""}`}>
      <div className="liber-hist-group-head">
        <button
          type="button"
          className="liber-hist-group-toggle"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          <span className={`liber-hist-chev${open ? " is-open" : ""}`}>
            <IconChevron size={12} />
          </span>
          <span className="liber-hist-group-ico" aria-hidden>
            <IconFolder size={13} />
          </span>
          {renaming ? (
            <input
              className="liber-hist-rename"
              value={nameDraft}
              autoFocus
              maxLength={40}
              onClick={(e) => e.stopPropagation()}
              onChange={(e) => setNameDraft(e.target.value)}
              onBlur={() => {
                onRename(nameDraft);
                setRenaming(false);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  onRename(nameDraft);
                  setRenaming(false);
                }
                if (e.key === "Escape") setRenaming(false);
              }}
            />
          ) : (
            <span className="liber-hist-group-title">{title}</span>
          )}
          <span className="liber-hist-group-count">{items.length}</span>
        </button>
        <div className="liber-hist-group-tools">
          <button
            type="button"
            className="liber-hist-act"
            title="Переименовать"
            aria-label="Переименовать папку"
            onClick={() => {
              setNameDraft(title);
              setRenaming(true);
            }}
          >
            <span className="liber-hist-act-glyph" aria-hidden>
              Aa
            </span>
          </button>
          <button
            type="button"
            className="liber-hist-act liber-hist-act-danger"
            title="Удалить папку"
            aria-label="Удалить папку"
            onClick={async () => {
              const ok = await confirm({
                title: "Удалить папку?",
                eyebrow: "папка · удаление",
                message: `Удалить папку «${title}»? Все отчёты и чаты сохранятся в истории.`,
                confirmLabel: "Удалить папку",
                danger: true,
              });
              if (ok) {
                onDelete();
              }
            }}
          >
            ×
          </button>
        </div>
      </div>
      {open ? (
        <ul className="liber-hist-list">
          {items.length === 0 ? (
            <li className="liber-hist-empty-folder">Пусто</li>
          ) : (
            items.map((h) => (
              <HistoryRow
                key={h.id}
                item={h}
                folders={folders}
                busy={busy}
                onOpen={() => onOpenHistory(h)}
                onTogglePin={() => onTogglePin(h.runId)}
                onMoveToFolder={(fid) => onMoveToFolder(h.runId, fid)}
              />
            ))
          )}
        </ul>
      ) : null}
    </section>
  );
}

function SectionLabel({ children }: { children: string }) {
  return <p className="liber-hist-section-label liber-side-label">{children}</p>;
}

export function Sidebar({
  collapsed,
  onToggle,
  healthReady,
  healthLabel,
  healthHint,
  imageChipLabel,
  imageChipOk = false,
  imageChipHint = "",
  history,
  folders,
  onNew,
  onOpenHistory,
  onTogglePin,
  onMoveToFolder,
  onCreateFolder,
  onRenameFolder,
  onDeleteFolder,
  onSettings,
  busy = false,
}: Props) {
  const [creating, setCreating] = useState(false);
  const [folderName, setFolderName] = useState("");

  const pinned = useMemo(
    () => history.filter((h) => h.pinned),
    [history],
  );
  const unpinned = useMemo(
    () => history.filter((h) => !h.pinned),
    [history],
  );
  const loose = useMemo(
    () => unpinned.filter((h) => !h.folderId),
    [unpinned],
  );

  const submitFolder = () => {
    const n = folderName.trim();
    if (!n) {
      setCreating(false);
      return;
    }
    onCreateFolder(n);
    setFolderName("");
    setCreating(false);
  };

  return (
    <aside
      className={`liber-sidebar${collapsed ? " is-collapsed" : ""}`}
      aria-label="Навигация Liber"
    >
      <div className="liber-sidebar-top">
        <div className="liber-sidebar-brand">
          <IconLiberMark size={collapsed ? 26 : 30} />
          <div
            className="liber-sidebar-brand-text liber-side-label"
            aria-hidden={collapsed}
          >
            <span className="liber-sidebar-word">Liber</span>
            <span
              className={`liber-sidebar-live${healthReady ? " ok" : ""}`}
              title={healthHint}
            >
              <span className="health-dot" aria-hidden />
              {healthLabel}
            </span>
          </div>
        </div>
        <button
          type="button"
          className="liber-sidebar-collapse"
          onClick={onToggle}
          aria-label={collapsed ? "Развернуть меню" : "Свернуть меню"}
          title={collapsed ? "Развернуть" : "Свернуть"}
        >
          <IconPanelLeft size={16} />
        </button>
      </div>

      <button
        type="button"
        className="liber-sidebar-new"
        disabled={busy}
        onClick={onNew}
        title="Новый чат"
        aria-label="Новый чат"
      >
        <IconPlus size={16} />
        <span className="liber-side-label">Новый чат</span>
      </button>

      {!collapsed ? (
        <div className="liber-sidebar-history" role="navigation" aria-label="Чаты">
          {history.length === 0 && folders.length === 0 ? (
            <p className="liber-sidebar-history-empty">
              Пока пусто — соберите первый отчёт.
            </p>
          ) : (
            <div className="liber-hist-stack">
              {pinned.length > 0 ? (
                <div className="liber-hist-section">
                  <SectionLabel>Закреплённые</SectionLabel>
                  <ul className="liber-hist-flat">
                    {pinned.map((h) => (
                      <HistoryRow
                        key={h.id}
                        item={h}
                        folders={folders}
                        busy={busy}
                        onOpen={() => onOpenHistory(h)}
                        onTogglePin={() => onTogglePin(h.runId)}
                        onMoveToFolder={(fid) => onMoveToFolder(h.runId, fid)}
                      />
                    ))}
                  </ul>
                </div>
              ) : null}

              <div className="liber-hist-section">
                <div className="liber-hist-section-head">
                  <SectionLabel>Папки</SectionLabel>
                  {!creating ? (
                    <button
                      type="button"
                      className="liber-hist-add-folder"
                      onClick={() => setCreating(true)}
                      title="Новая папка"
                      aria-label="Новая папка"
                    >
                      <span className="liber-hist-add-ico" aria-hidden>
                        <IconPlus size={11} />
                      </span>
                    </button>
                  ) : null}
                </div>
                {creating ? (
                  <form
                    className="liber-hist-create"
                    onSubmit={(e) => {
                      e.preventDefault();
                      submitFolder();
                    }}
                  >
                    <span className="liber-hist-create-icon" aria-hidden>
                      <IconFolder size={15} />
                    </span>
                    <input
                      value={folderName}
                      onChange={(e) => setFolderName(e.target.value)}
                      placeholder="Название папки…"
                      maxLength={40}
                      autoFocus
                      aria-label="Название папки"
                    />
                    <button
                      type="submit"
                      className="liber-hist-create-go"
                      disabled={!folderName.trim()}
                    >
                      Создать
                    </button>
                    <button
                      type="button"
                      className="liber-hist-create-cancel"
                      aria-label="Отмена"
                      title="Отмена"
                      onClick={() => {
                        setCreating(false);
                        setFolderName("");
                      }}
                    >
                      ×
                    </button>
                  </form>
                ) : null}
                {folders.length === 0 && !creating ? (
                  <p className="liber-hist-hint liber-side-label">Нет папок</p>
                ) : (
                  <div className="liber-hist-folders">
                    {folders.map((f) => {
                      const folderItems = historyInFolder(history, f.id);
                      return (
                        <FolderBlock
                          key={f.id}
                          title={f.name}
                          folderId={f.id}
                          items={folderItems}
                          folders={folders}
                          onOpenHistory={onOpenHistory}
                          onTogglePin={onTogglePin}
                          onMoveToFolder={onMoveToFolder}
                          onRename={(name) => onRenameFolder(f.id, name)}
                          onDelete={() => onDeleteFolder(f.id)}
                          busy={busy}
                        />
                      );
                    })}
                  </div>
                )}
              </div>

              {loose.length > 0 ? (
                <div className="liber-hist-section">
                  <SectionLabel>Недавние</SectionLabel>
                  <ul className="liber-hist-flat">
                    {loose.map((h) => (
                      <HistoryRow
                        key={h.id}
                        item={h}
                        folders={folders}
                        busy={busy}
                        onOpen={() => onOpenHistory(h)}
                        onTogglePin={() => onTogglePin(h.runId)}
                        onMoveToFolder={(fid) => onMoveToFolder(h.runId, fid)}
                      />
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          )}
        </div>
      ) : null}

      <div className="liber-sidebar-foot">
        {imageChipLabel ? (
          <span
            className={`liber-image-chip${imageChipOk ? " is-ok" : " is-down"}`}
            title={imageChipHint || imageChipLabel}
            role="status"
          >
            <span className="health-dot" aria-hidden />
            <span className="liber-side-label">{imageChipLabel}</span>
          </span>
        ) : null}
        <button
          type="button"
          className="liber-sidebar-item liber-sidebar-settings"
          onClick={onSettings}
          title="Настройки"
          aria-label="Настройки"
        >
          <IconSettings size={17} />
          <span className="liber-side-label">Настройки</span>
        </button>
        <span className="liber-sidebar-foot-dot" aria-hidden />
      </div>
    </aside>
  );
}
