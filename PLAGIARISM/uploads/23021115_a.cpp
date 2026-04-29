#include <iostream>
using namespace std;

float doMath(float x, float y, char op) {
    if (op == '+') return x + y;
    else if (op == '-') return x - y;
    else if (op == '*') return x * y;
    else if (op == '/') return (y != 0) ? x / y : 0;
    return 0;
}

int main() {
    cout << doMath(10, 5, '+') << endl;
    return 0;
}
