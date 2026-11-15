import httpx

base = 'http://localhost:8001/api/curriculum/v2'
r = httpx.get(f'{base}/books?class_num=11&subject=physics')
books = r.json().get('items', [])
print('Found Class 11 Physics books:', len(books))
for b in books:
    code = b['code']
    print(' ', code, b['title'])
    r_ch = httpx.get(f'{base}/books/{code}/chapters')
    chapters = r_ch.json()
    print('   Chapters count:', len(chapters))
    for ch in chapters[:3]:
        print('    -', ch.get('official_number'), ch.get('title'))
    if chapters:
        first_id = chapters[0]['id']
        r_tree = httpx.get(f'{base}/books/{code}/tree?max_level=subtopic')
        tree = r_tree.json()
        print('   Tree nodes count:', len(tree))
        if tree and 'nodes' in tree[0]:
            print('   Subtopics/topics count:', len(tree[0]['nodes']))
            for n in tree[0]['nodes'][:3]:
                print('      *', n.get('title'))
