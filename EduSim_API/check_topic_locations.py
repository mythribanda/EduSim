from app.src.modules.legacy_rag.vector_loader import vector_store
vector_store.load_all()

# Search for snell or refraction across all classes in physics
res = vector_store.retrieve('snell law refraction', subject='physics', k=5)
print('Unconstrained search for Snell law:')
for r in res:
    print(f"  Class {r.get('class')} | Book: {r.get('book_title')} | Ch: {r.get('chapter')} | Score: {r.get('score'):.4f}")

# Search for ohm law across all classes in physics
res = vector_store.retrieve('ohm law electric current voltage', subject='physics', k=5)
print('\nUnconstrained search for Ohm law:')
for r in res:
    print(f"  Class {r.get('class')} | Book: {r.get('book_title')} | Ch: {r.get('chapter')} | Score: {r.get('score'):.4f}")

# Search for mendel inheritance in biology
res = vector_store.retrieve('mendel laws inheritance', subject='biology', k=5)
print('\nUnconstrained search for Mendel laws:')
for r in res:
    print(f"  Class {r.get('class')} | Book: {r.get('book_title')} | Ch: {r.get('chapter')} | Score: {r.get('score'):.4f}")
