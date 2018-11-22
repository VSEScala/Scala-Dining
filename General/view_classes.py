import math


class PageListView:
    context = {}
    length = 10

    def set_up_list(self, entries, page):
        lower_bound = self.length * (page - 1)
        upper_bound = self.length * page

        self.context['entries'] = entries[lower_bound:upper_bound]
        self.context['page'] = page
        self.context['pages'] = math.ceil(len(entries) / self.length)
        #self.context['target'] = association
        if self.context['pages'] > 1:
            self.context['show_page_navigation'] = True
            self.context['pages'] = range(1, self.context['pages']+1)