class MeiteiKeyboard {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.onCharAdded = null;
        this.init();
    }

    init() {
        const charSets = {
            'Epee Mayek': ['ꯀ','ꯁ','ꯂ','ꯃ','ꯄ','ꯅ','ꯆ','ꯇ','ꯈ','ꯉ','ꯊ','ꯋ','ꯌ','ꯍ','ꯎ','ꯏ','ꯐ','ꯑ','ꯒ','ꯓ','ꯔ','ꯕ','ꯖ','ꯗ','ꯘ','ꯙ','ꯚ'],
            'Lonsum': ['ꯛ','ꯜ','ꯝ','ꯞ','ꯟ','ꯠ','ꯡ','ꯢ'],
            'Vowels': ['ꯑ','ꯏ','ꯎ','ꯑꯥ','ꯑꯤ','ꯑꯨ','ꯑꯦ','ꯑꯩ','ꯑꯣ','ꯑꯧ'],
            'Cheitap Mayek': ['ꯥ','ꯤ','ꯨ','ꯦ','ꯩ','ꯣ','ꯧ','ꯪ'],
            'Digits': ['꯰','꯱','꯲','꯳','꯴','꯵','꯶','꯷','꯸','꯹'],
            'Other': ['꯫','꯬','꯭']
        };
        for (let [category, chars] of Object.entries(charSets)) {
            let row = document.createElement('div');
            row.className = 'mb-2';
            let label = document.createElement('strong');
            label.innerText = category + ': ';
            row.appendChild(label);
            for (let ch of chars) {
                let btn = document.createElement('button');
                btn.innerText = ch;
                btn.className = 'btn btn-sm btn-outline-secondary keyboard-btn';
                btn.onclick = () => {
                    if (this.onCharAdded) this.onCharAdded(ch);
                };
                row.appendChild(btn);
            }
            this.container.appendChild(row);
        }
    }
}