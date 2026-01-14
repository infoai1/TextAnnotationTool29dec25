"""
GroupManager - Smart paragraph grouping for LightRAG export.

Handles creation, validation, and manipulation of paragraph groups.
Groups are 512-800 token chunks for optimal retrieval performance.
"""

from typing import List, Dict, Optional, Tuple
import helpers


class GroupManager:
    """
    Manage paragraph groups with smart algorithms.

    **Purpose**: Create groups of paragraphs (512-800 tokens) for LightRAG export.
    Each group becomes a chunk in the knowledge graph.

    **Key Methods**:
    - create_groups_for_chapter(): Smart grouping algorithm
    - validate_group(): Check if group meets token requirements
    - merge_groups(): Combine two groups
    - split_group_at_paragraph(): Split group at specific paragraph
    """

    def __init__(self, min_tokens: int = 512, max_tokens: int = 800, hard_limit: int = 1000):
        """
        Initialize GroupManager with token limits.

        Args:
            min_tokens: Minimum tokens per group (default 512)
            max_tokens: Ideal maximum (default 800)
            hard_limit: Never exceed this (default 1000)
        """
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.hard_limit = hard_limit


    def create_groups_for_chapter(
        self,
        paragraphs: List[Dict],
        chapter_title: str,
        group_counter_start: int = 0
    ) -> Tuple[List[Dict], int]:
        """
        Smart grouping algorithm: Creates 512-800 token chunks.

        **Rules**:
        1. Subheading starts new group (if current >= 512 tokens)
        2. Single para > 800 tokens → isolated group
        3. Would exceed 1000 tokens → flush current group
        4. Would exceed 800 and current >= 512 → flush first
        5. Never cross chapter boundary

        Args:
            paragraphs: List of paragraph dicts with 'text', 'type', 'page_info'
            chapter_title: Used for group metadata
            group_counter_start: Starting counter for group IDs

        Returns:
            Tuple of (groups list, next counter value)

        Example:
            manager = GroupManager()
            groups, next_counter = manager.create_groups_for_chapter(
                paragraphs=[{id: 1, text: '...'}],
                chapter_title='Introduction',
                group_counter_start=0
            )
        """
        if not paragraphs:
            return [], group_counter_start

        groups = []
        current_group = {
            'para_ids': [],
            'texts': [],
            'token_count': 0,
            'page_start': None,
            'page_end': None
        }
        group_counter = group_counter_start

        def flush_group():
            """Flush current group to groups list."""
            nonlocal group_counter, current_group
            if current_group['para_ids']:
                group_counter += 1
                groups.append({
                    'group_id': f"g_{group_counter:03d}",
                    'para_ids': current_group['para_ids'],
                    'combined_text': '\n\n'.join(current_group['texts']),
                    'token_count': current_group['token_count'],
                    'chapter': chapter_title,
                    'page_start': current_group['page_start'],
                    'page_end': current_group['page_end']
                })
            current_group = {
                'para_ids': [], 'texts': [], 'token_count': 0,
                'page_start': None, 'page_end': None
            }

        def add_para_to_group(para):
            """Add a paragraph to current group."""
            para_id = para.get('id')
            # Handle both numeric and string IDs
            if isinstance(para_id, int):
                para_id = f"p_{para_id:03d}"
            elif isinstance(para_id, str) and not para_id.startswith('p_'):
                para_id = f"p_{para_id}"

            current_group['para_ids'].append(para_id)
            current_group['texts'].append(para.get('text', ''))
            current_group['token_count'] += helpers.estimate_tokens(para.get('text', ''))

            page_info = para.get('page_info', {})
            page_num = page_info.get('page_number')
            if page_num:
                if current_group['page_start'] is None:
                    current_group['page_start'] = page_num
                current_group['page_end'] = page_num

        for para in paragraphs:
            # Skip empty paragraphs
            text = para.get('text', '').strip()
            if not text:
                continue

            para_tokens = helpers.estimate_tokens(text)
            is_subheading = para.get('type') == 'subheading' or para.get('is_subheading')

            # Subheading with existing content >= min_tokens: start new group
            if is_subheading and current_group['token_count'] >= self.min_tokens:
                flush_group()

            # Single para > max_tokens: isolate it
            if para_tokens > self.max_tokens:
                flush_group()
                add_para_to_group(para)
                flush_group()
                continue

            # Would exceed hard_limit? Flush first
            if current_group['token_count'] + para_tokens > self.hard_limit:
                flush_group()

            # Would exceed max_tokens and current is already substantial? Flush first
            if current_group['token_count'] >= self.min_tokens and \
               current_group['token_count'] + para_tokens > self.max_tokens:
                flush_group()

            add_para_to_group(para)

        # Flush final group
        flush_group()

        return groups, group_counter


    def recalculate_stats(self, group: Dict, paragraphs: List[Dict]) -> Dict:
        """
        Recalculate token count and page range for group.

        Call this after:
        - Adding/removing paragraphs from group
        - Editing paragraph text
        - Merging groups

        Args:
            group: Group dict with 'para_ids'
            paragraphs: All paragraphs (to look up by ID)

        Returns:
            Updated group dict
        """
        # Create lookup map
        para_map = {p.get('id'): p for p in paragraphs if 'id' in p}
        # Handle string IDs with p_ prefix
        for p in paragraphs:
            pid = p.get('id')
            if isinstance(pid, int):
                para_map[f"p_{pid:03d}"] = p

        total_tokens = 0
        page_start = None
        page_end = None

        for para_id in group.get('para_ids', []):
            para = para_map.get(para_id)
            if para and not para.get('deleted'):
                total_tokens += helpers.estimate_tokens(para.get('text', ''))
                page_num = para.get('page_info', {}).get('page_number')
                if page_num:
                    if page_start is None or page_num < page_start:
                        page_start = page_num
                    if page_end is None or page_num > page_end:
                        page_end = page_num

        group['token_count'] = total_tokens
        group['page_start'] = page_start
        group['page_end'] = page_end

        return group


    def validate_group(self, group: Dict) -> str:
        """
        Validate group and return status.

        **Status levels**:
        - 'optimal': 512-800 tokens (ideal range)
        - 'acceptable': 200-512 or 800-1000 tokens (okay)
        - 'warning': < 200 or > 1000 tokens (needs attention)

        Args:
            group: Group dict with 'token_count'

        Returns:
            Status string: 'optimal', 'acceptable', or 'warning'
        """
        tokens = group.get('token_count', 0)
        if self.min_tokens <= tokens <= self.max_tokens:
            return 'optimal'
        elif 200 <= tokens < self.min_tokens or self.max_tokens < tokens <= self.hard_limit:
            return 'acceptable'
        else:
            return 'warning'


    def move_paragraph_to_group(
        self,
        para_id: str,
        target_group_id: str,
        paragraphs: List[Dict],
        groups: List[Dict]
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Move paragraph from its current group to target group.

        Args:
            para_id: Paragraph ID to move
            target_group_id: Destination group ID
            paragraphs: All paragraphs
            groups: All groups

        Returns:
            Tuple of (updated paragraphs, updated groups)
        """
        # Find paragraph
        para = None
        for p in paragraphs:
            pid = p.get('id')
            if isinstance(pid, int):
                pid = f"p_{pid:03d}"
            if pid == para_id:
                para = p
                break

        if not para:
            return paragraphs, groups

        old_group_id = para.get('group_id')

        # Remove from old group
        if old_group_id:
            for group in groups:
                if group.get('group_id') == old_group_id:
                    if para_id in group.get('para_ids', []):
                        group['para_ids'].remove(para_id)
                        self.recalculate_stats(group, paragraphs)
                    break

        # Add to new group
        for group in groups:
            if group.get('group_id') == target_group_id:
                if para_id not in group.get('para_ids', []):
                    group['para_ids'].append(para_id)
                para['group_id'] = target_group_id
                self.recalculate_stats(group, paragraphs)
                break

        # Cleanup empty groups
        groups = [g for g in groups if len(g.get('para_ids', [])) > 0]

        return paragraphs, groups


    def merge_groups(
        self,
        group_id_1: str,
        group_id_2: str,
        paragraphs: List[Dict],
        groups: List[Dict]
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Merge two groups into one.

        Combines para_ids, updates paragraph references, recalculates stats.

        Args:
            group_id_1: First group (will contain merged result)
            group_id_2: Second group (will be removed)
            paragraphs: All paragraphs
            groups: All groups

        Returns:
            Tuple of (updated paragraphs, updated groups)
        """
        g1 = None
        g2 = None

        for g in groups:
            if g.get('group_id') == group_id_1:
                g1 = g
            if g.get('group_id') == group_id_2:
                g2 = g

        if not g1 or not g2:
            return paragraphs, groups

        # Combine para_ids (maintain order)
        g1['para_ids'].extend(g2['para_ids'])

        # Update paragraphs to point to g1
        for para_id in g2['para_ids']:
            for p in paragraphs:
                pid = p.get('id')
                if isinstance(pid, int):
                    pid = f"p_{pid:03d}"
                if pid == para_id:
                    p['group_id'] = group_id_1
                    break

        # Recalculate stats
        self.recalculate_stats(g1, paragraphs)

        # Remove g2
        groups = [g for g in groups if g.get('group_id') != group_id_2]

        return paragraphs, groups


    def split_group_at_paragraph(
        self,
        para_id: str,
        paragraphs: List[Dict],
        groups: List[Dict]
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Split group at specific paragraph.

        Creates two groups:
        - Group 1: All paras before split point
        - Group 2: Split para and all paras after

        Args:
            para_id: Paragraph ID to split at
            paragraphs: All paragraphs
            groups: All groups

        Returns:
            Tuple of (updated paragraphs, updated groups)
        """
        # Find paragraph and its group
        para = None
        old_group = None

        for p in paragraphs:
            pid = p.get('id')
            if isinstance(pid, int):
                pid = f"p_{pid:03d}"
            if pid == para_id:
                para = p
                break

        if not para:
            return paragraphs, groups

        group_id = para.get('group_id')
        if not group_id:
            return paragraphs, groups

        for g in groups:
            if g.get('group_id') == group_id:
                old_group = g
                break

        if not old_group:
            return paragraphs, groups

        # Find split index
        split_idx = old_group['para_ids'].index(para_id)

        # Create two new groups
        para_ids_before = old_group['para_ids'][:split_idx]
        para_ids_after = old_group['para_ids'][split_idx:]

        if not para_ids_before:  # Nothing to split
            return paragraphs, groups

        # Generate new group ID
        max_counter = 0
        for g in groups:
            gid = g.get('group_id', '')
            if gid.startswith('g_'):
                try:
                    counter = int(gid.split('_')[1])
                    max_counter = max(max_counter, counter)
                except:
                    pass
        new_group_id = f"g_{max_counter + 1:03d}"

        # Update old group (keep first part)
        old_group['para_ids'] = para_ids_before
        self.recalculate_stats(old_group, paragraphs)

        # Create new group (second part)
        new_group = {
            'group_id': new_group_id,
            'para_ids': para_ids_after,
            'chapter': old_group.get('chapter', ''),
        }
        self.recalculate_stats(new_group, paragraphs)
        groups.append(new_group)

        # Update paragraph group references
        for pid in para_ids_after:
            for p in paragraphs:
                p_id = p.get('id')
                if isinstance(p_id, int):
                    p_id = f"p_{p_id:03d}"
                if p_id == pid:
                    p['group_id'] = new_group_id
                    break

        return paragraphs, groups


    def generate_groups(
        self,
        paragraphs: List[Dict],
        structure: List[Dict] = None
    ) -> List[Dict]:
        """
        High-level: Generate all groups for entire book.

        Iterates through chapters, creates groups for each.

        Args:
            paragraphs: All paragraphs
            structure: Book structure with chapters (optional)

        Returns:
            List of all groups
        """
        all_groups = []
        group_counter = 0

        if structure:
            # Group by chapter
            for chapter in structure:
                if chapter.get('type') == 'chapter':
                    chapter_paras = chapter.get('paragraphs', [])
                    groups, group_counter = self.create_groups_for_chapter(
                        chapter_paras,
                        chapter.get('title', 'Untitled'),
                        group_counter
                    )
                    all_groups.extend(groups)
        else:
            # No structure - treat all as one chapter
            groups, _ = self.create_groups_for_chapter(
                paragraphs,
                'Book',
                0
            )
            all_groups.extend(groups)

        return all_groups


    def get_group_stats(self, groups: List[Dict]) -> Dict:
        """
        Get statistics about groups (for debugging/UI).

        Returns:
            Dict with counts by status
        """
        stats = {
            'total': len(groups),
            'optimal': 0,
            'acceptable': 0,
            'warning': 0
        }

        for group in groups:
            status = self.validate_group(group)
            stats[status] += 1

        return stats
