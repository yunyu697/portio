//! 标签页模型：多标签会话的纯规则层，不碰 UI。
//!
//! 规则都写成可测的函数，界面上只做渲染与转发：
//! - 关掉当前标签后，焦点落到右边的邻居（没有就往左），这符合浏览器与 Xshell 的共同习惯；
//! - 标签数量有上限，超了返回 `TooManyTabs`，由调用方决定是先提示还是先关旧标签；
//! - 标签 id 单调递增，不复用，这样异步回调按 id 找标签不会找错。

use crate::session::SessionId;
use crate::CoreError;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
pub struct TabId(pub u64);

impl std::fmt::Display for TabId {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "tab-{}", self.0)
    }
}

/// 一个标签代表一个终端。`session` 为 `None` 表示本地终端（尚未实现对端）。
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Tab {
    pub id: TabId,
    pub title: String,
    pub session: Option<SessionId>,
    pub pinned: bool,
}

/// 默认上限。个人工具一次开十几个标签足够，再多就是真的该看会话栏了。
pub const DEFAULT_MAX_TABS: usize = 16;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TabSet {
    tabs: Vec<Tab>,
    active: Option<TabId>,
    next_id: u64,
    max: usize,
}

impl Default for TabSet {
    fn default() -> Self {
        Self::new(DEFAULT_MAX_TABS)
    }
}

impl TabSet {
    pub fn new(max: usize) -> Self {
        Self {
            tabs: Vec::new(),
            active: None,
            next_id: 1,
            max: max.max(1),
        }
    }

    pub fn len(&self) -> usize {
        self.tabs.len()
    }

    pub fn is_empty(&self) -> bool {
        self.tabs.is_empty()
    }

    pub fn max(&self) -> usize {
        self.max
    }

    pub fn tabs(&self) -> &[Tab] {
        &self.tabs
    }

    pub fn active(&self) -> Option<TabId> {
        self.active
    }

    pub fn active_tab(&self) -> Option<&Tab> {
        self.active.and_then(|id| self.get(id))
    }

    pub fn get(&self, id: TabId) -> Option<&Tab> {
        self.tabs.iter().find(|t| t.id == id)
    }

    pub fn position(&self, id: TabId) -> Option<usize> {
        self.tabs.iter().position(|t| t.id == id)
    }

    /// 新开一个标签，并立即把它设为当前。返回新标签的 id。
    pub fn open(
        &mut self,
        title: impl Into<String>,
        session: Option<SessionId>,
    ) -> Result<TabId, CoreError> {
        if self.tabs.len() >= self.max {
            return Err(CoreError::TooManyTabs(self.max));
        }
        let title = title.into();
        let title = title.trim().to_string();
        if title.is_empty() {
            return Err(CoreError::EmptyName);
        }
        let id = TabId(self.next_id);
        self.next_id += 1;
        self.tabs.push(Tab {
            id,
            title,
            session,
            pinned: false,
        });
        self.active = Some(id);
        Ok(id)
    }

    /// 切到某个标签。找不到返回 `NotFound`，当前标签保持不变。
    pub fn activate(&mut self, id: TabId) -> Result<(), CoreError> {
        if self.get(id).is_none() {
            return Err(CoreError::NotFound(SessionId(id.to_string())));
        }
        self.active = Some(id);
        Ok(())
    }

    /// 关掉一个标签，返回关闭后应处于前台的标签。
    ///
    /// 只有关掉的正是当前标签时才移动焦点：优先右边邻居，没有就左边。
    pub fn close(&mut self, id: TabId) -> Result<Option<TabId>, CoreError> {
        let pos = self
            .position(id)
            .ok_or_else(|| CoreError::NotFound(SessionId(id.to_string())))?;
        self.tabs.remove(pos);
        if self.active == Some(id) {
            self.active = self
                .tabs
                .get(pos)
                .or_else(|| self.tabs.get(pos.wrapping_sub(1)).filter(|_| pos > 0))
                .map(|t| t.id);
        }
        Ok(self.active)
    }

    /// 拖动排序：把某个标签移动到 `to` 位置（越界会被夹到两端）。
    pub fn move_to(&mut self, id: TabId, to: usize) -> Result<(), CoreError> {
        let from = self
            .position(id)
            .ok_or_else(|| CoreError::NotFound(SessionId(id.to_string())))?;
        let to = to.min(self.tabs.len().saturating_sub(1));
        if from == to {
            return Ok(());
        }
        let tab = self.tabs.remove(from);
        self.tabs.insert(to, tab);
        Ok(())
    }

    /// 改标题。会话握手成功后，标题会从“新建连接”变成 `user@host`。
    pub fn rename(&mut self, id: TabId, title: impl Into<String>) -> Result<(), CoreError> {
        let title = title.into();
        let title = title.trim().to_string();
        if title.is_empty() {
            return Err(CoreError::EmptyName);
        }
        let tab = self
            .tabs
            .iter_mut()
            .find(|t| t.id == id)
            .ok_or_else(|| CoreError::NotFound(SessionId(id.to_string())))?;
        tab.title = title;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sid(s: &str) -> Option<SessionId> {
        Some(SessionId(s.to_string()))
    }

    #[test]
    fn open_sets_active_and_increments_id() {
        let mut set = TabSet::default();
        let a = set.open("本地", None).unwrap();
        let b = set.open("web-01", sid("s1")).unwrap();
        assert_eq!(set.len(), 2);
        assert_eq!(set.active(), Some(b));
        assert!(a < b, "标签 id 必须单调递增");
        assert_eq!(set.tabs()[1].session, sid("s1"));
    }

    #[test]
    fn open_rejects_empty_title() {
        let mut set = TabSet::default();
        assert_eq!(set.open("   ", None), Err(CoreError::EmptyName));
        assert!(set.is_empty());
    }

    #[test]
    fn open_respects_max() {
        let mut set = TabSet::new(2);
        set.open("a", None).unwrap();
        set.open("b", None).unwrap();
        assert_eq!(set.open("c", None), Err(CoreError::TooManyTabs(2)));
        assert_eq!(set.len(), 2);
    }

    #[test]
    fn close_active_moves_focus_right() {
        let mut set = TabSet::default();
        let _a = set.open("a", None).unwrap();
        let b = set.open("b", None).unwrap();
        let c = set.open("c", None).unwrap();
        set.activate(b).unwrap();
        let next = set.close(b).unwrap();
        assert_eq!(next, Some(c), "关掉当前标签后应落到右邻居");
        assert_eq!(set.active(), Some(c));
        assert_eq!(set.len(), 2);
    }

    #[test]
    fn close_last_active_moves_focus_left() {
        let mut set = TabSet::default();
        let a = set.open("a", None).unwrap();
        let b = set.open("b", None).unwrap();
        set.activate(b).unwrap();
        let next = set.close(b).unwrap();
        assert_eq!(next, Some(a), "最右侧被关掉时应落到左邻居");
    }

    #[test]
    fn close_only_tab_leaves_empty() {
        let mut set = TabSet::default();
        let a = set.open("a", None).unwrap();
        assert_eq!(set.close(a).unwrap(), None);
        assert_eq!(set.active(), None);
        assert!(set.is_empty());
    }

    #[test]
    fn close_inactive_keeps_active() {
        let mut set = TabSet::default();
        let a = set.open("a", None).unwrap();
        let b = set.open("b", None).unwrap();
        set.activate(b).unwrap();
        assert_eq!(set.close(a).unwrap(), Some(b));
        assert_eq!(set.active(), Some(b));
    }

    #[test]
    fn close_unknown_is_not_found() {
        let mut set = TabSet::default();
        set.open("a", None).unwrap();
        assert!(matches!(set.close(TabId(99)), Err(CoreError::NotFound(_))));
        assert_eq!(set.len(), 1);
    }

    #[test]
    fn activate_unknown_is_not_found_and_keeps_current() {
        let mut set = TabSet::default();
        let a = set.open("a", None).unwrap();
        set.activate(TabId(42)).unwrap_err();
        assert_eq!(set.active(), Some(a));
    }

    #[test]
    fn move_to_clamps_and_keeps_active() {
        let mut set = TabSet::default();
        let a = set.open("a", None).unwrap();
        let _b = set.open("b", None).unwrap();
        let c = set.open("c", None).unwrap();
        set.activate(a).unwrap();
        set.move_to(c, 0).unwrap();
        assert_eq!(set.tabs()[0].id, c);
        assert_eq!(set.active(), Some(a), "排序不应改变当前标签");
        set.move_to(c, 99).unwrap();
        assert_eq!(set.tabs().last().unwrap().id, c);
    }

    #[test]
    fn rename_validates_title() {
        let mut set = TabSet::default();
        let a = set.open("临时", None).unwrap();
        set.rename(a, "root@web-01").unwrap();
        assert_eq!(set.get(a).unwrap().title, "root@web-01");
        assert_eq!(set.rename(a, " "), Err(CoreError::EmptyName));
        assert_eq!(
            set.rename(TabId(7), "x").unwrap_err(),
            CoreError::NotFound(SessionId("tab-7".into()))
        );
    }
}
