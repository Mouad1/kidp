with open('dashboard/templates/book.html') as f:
    text = f.read()

import re
text = re.sub(r'src="/api/book/\$\{book\}/open-image\?filename=\$\{img\}"[^>]+onerror="this\.src=\'' + r'\/images/\$\{book\}/\$\{img\}' + r'\'"', r'src="/images/${book}/${img}"  style="pointer-events: none; width: 100%; height: 100%; object-fit: cover;"', text)

with open('dashboard/templates/book.html', 'w') as f:
    f.write(text)
