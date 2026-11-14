with open('scripts/supabase_migration_payload.sql', 'r', encoding='utf-8') as f:
    text = f.read()

parts = text.split('DO $$')
header = parts[0]
blocks = ['DO $$' + p for p in parts[1:]]

print(f"Total order blocks found: {len(blocks)}")

chunk1 = header + '\n'.join(blocks[:20]) + '\nCOMMIT;'
chunk2 = 'BEGIN;\n' + '\n'.join(blocks[20:40]) + '\nCOMMIT;'
chunk3 = 'BEGIN;\n' + '\n'.join(blocks[40:]) # includes expense insert & COMMIT

with open('scripts/chunk1.sql', 'w', encoding='utf-8') as f:
    f.write(chunk1)
with open('scripts/chunk2.sql', 'w', encoding='utf-8') as f:
    f.write(chunk2)
with open('scripts/chunk3.sql', 'w', encoding='utf-8') as f:
    f.write(chunk3)

print("Chunk 1 bytes:", len(chunk1))
print("Chunk 2 bytes:", len(chunk2))
print("Chunk 3 bytes:", len(chunk3))
