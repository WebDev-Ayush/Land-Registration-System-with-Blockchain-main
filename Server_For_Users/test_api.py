import requests, json

r = requests.post('http://127.0.0.1:5003/api/recommend', json={
    'budget': 5,
    'minArea': 1000,
    'bedrooms': 3,
    'bathrooms': 2,
    'propertyType': 'apartment',
    'areaType': 'urban',
    'facilities': ['school', 'hospital', 'metro'],
    'furnished': 'semi-furnished',
    'parking': True,
    'yearBuilt': 2020
})

d = r.json()
print('Status:', r.status_code)
print('Count:', d.get('count', 0))
for x in d.get('results', []):
    print(f"  [{x['matchScore']}%] {x['title']} - {x['price']} ETH")
