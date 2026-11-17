"""Export ATTopic"""

from collective.exportimport.export_content import ExportContent


class ExportTopic(ExportContent):
    """Export ATTopic"""

    def build_query(self):
        """Build the query based on the topic criteria"""
        return self.context.buildQuery()
