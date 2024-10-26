 class PersistLogins {

    constructor(storage) {
        this.storage = storage;
        this.loadFromStorage();
    }

    loadFromStorage() {
        const savedState = this.storage.getItem('auth');
        if (savedState) {
            this.auth = JSON.parse(savedState);
        }
    }

    saveToStorage(auth) {
        this.auth = auth;
        this.storage.setItem('auth', JSON.stringify(auth));
    }

    clearStorage() {
        this.storage.removeItem('auth');
    }
}
const  PersistLogin = ()=>{
    return new PersistLogins(localStorage);
}

export default PersistLogin;