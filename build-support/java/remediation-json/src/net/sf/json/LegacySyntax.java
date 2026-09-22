// Copyright 2026 AmbisGIS contributors. SPDX-License-Identifier: Apache-2.0
package net.sf.json;
import java.math.BigInteger;
import java.util.ArrayDeque;
import java.util.Deque;
/** Narrow lexical translation of observed legacy separators and integer literals.
 * Jackson retains responsibility for structural parsing, strings and bounds.
 */
final class LegacySyntax {
    private LegacySyntax() {}
    static String translate(String input) {
        StringBuilder output=new StringBuilder(input.length());
        Deque<Character> nesting=new ArrayDeque<Character>();
        int cursor=0;
        while(cursor<input.length()) {
            char ch=input.charAt(cursor);
            if(ch=='"' || ch=='\'') {
                int start=cursor++;boolean escaped=false;
                while(cursor<input.length()) {char current=input.charAt(cursor++);if(!escaped&&current==ch)break;if(!escaped&&current=='\\')escaped=true;else escaped=false;}
                output.append(input,start,cursor);continue;
            }
            if(ch=='/' && cursor+1<input.length() && (input.charAt(cursor+1)=='/' || input.charAt(cursor+1)=='*')) {
                int start=cursor;boolean line=input.charAt(cursor+1)=='/';cursor+=2;
                if(line){while(cursor<input.length()&&input.charAt(cursor)!='\n')cursor++;}
                else {while(cursor+1<input.length() && !(input.charAt(cursor)=='*'&&input.charAt(cursor+1)=='/'))cursor++;cursor=Math.min(input.length(),cursor+2);}
                output.append(input,start,cursor);continue;
            }
            if(Character.isWhitespace(ch)){output.append(ch);cursor++;continue;}
            if(ch=='['||ch=='{'){if(nesting.size()>=JsonSupport.maxDepth())throw new JSONException("JSON nesting limit exceeded");nesting.push(ch);output.append(ch);cursor++;continue;}
            if(ch==']'||ch=='}'){if(!nesting.isEmpty())nesting.pop();output.append(ch);cursor++;continue;}
            if(ch==';'){output.append(',');cursor++;continue;}
            if(ch=='='){output.append(':');cursor++;if(cursor<input.length()&&input.charAt(cursor)=='>')cursor++;continue;}
            if(ch==','||ch==':'){output.append(ch);cursor++;continue;}
            int start=cursor;
            while(cursor<input.length() && "\"'[]{} ,:;=".indexOf(input.charAt(cursor))<0 && !Character.isWhitespace(input.charAt(cursor)))cursor++;
            if(cursor==start){output.append(ch);cursor++;continue;}
            String atom=input.substring(start,cursor);
            int next=cursor;while(next<input.length()&&Character.isWhitespace(input.charAt(next)))next++;
            boolean key=next<input.length()&&(input.charAt(next)==':'||input.charAt(next)=='=');
            if(!key && atom.matches("[+-]?0[xX][0-9a-fA-F]+")) {
                if(atom.length()>1000)throw new JSONException("Legacy integer exceeds the numeric length limit");
                boolean negative=atom.startsWith("-");int prefix=atom.charAt(0)=='-'||atom.charAt(0)=='+' ? 3 : 2;
                BigInteger integer=new BigInteger(atom.substring(prefix),16);output.append(negative?integer.negate():integer);
            } else if(!key && atom.matches("[+-]?0[0-7]+")) { if(atom.length()>1000)throw new JSONException("Legacy integer exceeds the numeric length limit");output.append(new BigInteger(atom,8)); }
            else output.append(atom);
        }
        return output.toString();
    }
}
